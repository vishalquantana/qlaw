#!/usr/bin/env python3
"""Join India Code section text onto the CBIC statute hierarchy.

The CBIC API gave us the section *structure* (act, chapter, section number,
heading) but no wording — its records carry `contentData: null` and no content
endpoint exists. India Code has the wording, in its `Section` collection
(see `harvest_indiacode.py`).

This reads the harvested sections, indexes them by (normalised Act name,
normalised section number), and rewrites the matching `cbic_act_section` rows in
law.db with the real text. The CBIC API URL stays as `source_url` (it is where
the hierarchy came from) and the India Code URL is recorded in the body, so both
provenance chains survive.

Usage: python3 join_cbic_section_text.py --dry-run
       python3 join_cbic_section_text.py
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
SECTIONS = ROOT / "data" / "law" / "indiacode" / "sections.jsonl"
INDIA_CODE_ITEM = "https://indiacode.gov.in/server/api/core/items/{uuid}"


def _load_law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def norm_section(s: str) -> str:
    """'Section 11A' and '11A' are the same section."""
    s = re.sub(r"^\s*section\s*", "", (s or "").strip(), flags=re.I)
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


def load_sections() -> tuple[dict[tuple[str, str], dict], dict[str, list[dict]]]:
    """Return (by act+section, by section). The second index lets a row whose Act
    the CBIC hierarchy never recorded still be matched on its section number."""
    idx: dict[tuple[str, str], dict] = {}
    by_sec: dict[str, list[dict]] = {}
    if not SECTIONS.exists():
        return idx, by_sec
    for line in SECTIONS.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (norm(r.get("act_name", "")), norm_section(r.get("section_number", "")))
        idx.setdefault(key, r)
        by_sec.setdefault(norm_section(r.get("section_number", "")), []).append(r)
    return idx, by_sec


# The CBIC hierarchy titles some Acts differently from India Code. Both sides are
# normalised before comparison, so a mismatch here means the year or wording in the
# title genuinely differs — not just punctuation.
ACT_ALIASES = {
    # India Code carries this Act with the year 2023; section titles match the
    # CBIC rows 1:1, so it is the same Act.
    "provisional collection of taxes act 1931":
        "provisional collection of taxes act 2023",
}


def pick_by_title(cands: list[dict], title: str) -> dict | None:
    """Choose the candidate whose heading best overlaps the CBIC section heading."""
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    want = set(re.findall(r"[a-z]{4,}", (title or "").lower()))
    if not want:
        return None
    best, score = None, 0.0
    for c in cands:
        have = set(re.findall(r"[a-z]{4,}", (c.get("title") or "").lower()))
        if not have:
            continue
        overlap = len(want & have) / len(want | have)
        if overlap > score:
            best, score = c, overlap
    # require a real overlap, not a coincidental shared word
    return best if score >= 0.34 else None


def act_and_section(body: str, number: str) -> tuple[str, str]:
    m = re.search(r"^Act:\s*(.+)$", body or "", re.M)
    return (m.group(1).strip() if m else "", norm_section(number))


def main(dry_run: bool = False) -> None:
    law_db = _load_law_db()
    idx, by_sec = load_sections()
    print(f"India Code sections indexed: {len(idx):,}")
    if not idx:
        sys.exit("no sections harvested — run harvest_indiacode.py first")

    con = law_db.init_db()
    con.row_factory = __import__("sqlite3").Row
    rows = con.execute(
        "SELECT id, source_url, kind, title, number, pub_date, local_path, sha256, body"
        " FROM documents WHERE kind='cbic_act_section' ORDER BY id").fetchall()
    print(f"CBIC section rows: {len(rows)}")

    matched = unmatched = 0
    recovered = 0
    miss_acts: dict[str, int] = {}
    for r in rows:
        act, sec = act_and_section(r["body"], r["number"])
        key = norm(act)
        hit = idx.get((ACT_ALIASES.get(key, key), sec))
        if not hit and not act:
            # the CBIC hierarchy recorded no Act for these rows, so there is
            # nothing to key on — fall back to the section number plus a heading
            # overlap, which is enough to identify them unambiguously
            hit = pick_by_title(by_sec.get(sec, []), r["title"])
            if hit:
                recovered += 1
        if not hit:
            unmatched += 1
            miss_acts[act or "(no act)"] = miss_acts.get(act or "(no act)", 0) + 1
            continue
        matched += 1
        if dry_run:
            continue
        text = hit["text"]
        # Where India Code titles the Act differently from the CBIC hierarchy
        # (e.g. the Provisional Collection of Taxes Act is titled 2023 there and
        # 1931 here), record both so the discrepancy is visible rather than hidden.
        src_act = (hit.get("act_name") or "").strip()
        act_line = (f"Act (India Code): {src_act}\n"
                    if src_act and norm(src_act) != norm(act) else "")
        # a recovered row had no Act recorded, so take the name from India Code
        shown_act = act or src_act
        body = (f"Section: {r['title']}\n"
                f"Act: {shown_act}\n"
                f"Section number: {hit['section_number']}\n"
                f"{act_line}"
                f"Text source: India Code ({INDIA_CODE_ITEM.format(uuid=hit['uuid'])})\n\n"
                f"{text}")
        law_db.upsert_document(con, {
            "source_url": r["source_url"], "kind": r["kind"], "title": r["title"],
            "number": r["number"], "pub_date": r["pub_date"],
            "local_path": r["local_path"],
            "sha256": hashlib.sha256(body.encode()).hexdigest(), "body": body})

    if not dry_run:
        con.commit()
    print(f"\nmatched {matched} / {len(rows)}  (unmatched {unmatched})")
    if miss_acts:
        print("unmatched by act:")
        for a, n in sorted(miss_acts.items(), key=lambda kv: -kv[1])[:12]:
            print(f"   {n:>4}  {a[:66]}")
    if dry_run:
        print("\n(dry run — nothing written)")
    else:
        with_text = con.execute(
            "SELECT COUNT(*) FROM documents WHERE kind='cbic_act_section'"
            " AND body LIKE '%Text source: India Code%'").fetchone()[0]
        print(f"cbic_act_section rows now carrying India Code text: {with_text}")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
