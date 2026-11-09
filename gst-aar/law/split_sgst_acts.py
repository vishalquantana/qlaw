#!/usr/bin/env python3
"""Split the State GST Acts into individual sections.

Why this matters: the evaluation harness showed that of 3,815 section citations in
the advance rulings, **2,385 — the majority — are to State GST Acts** (SGST s.98(4)
alone appears 350 times). We hold each State GST Act as one 100–600 KB document, so
none of those citations could be resolved to a section.

Splitting them is harder than the CGST Rules PDF because the source text differs:

  * every visual line is separated by a blank line, so the heading is not its own
    line — the text has to be flattened before headings can be found;
  * headings terminate with an em-dash (`1. Short title, extent and commencement.—`)
    rather than the `.-` used in the CGST Rules;
  * the tail of the document carries an amendment table whose entries also look like
    numbered headings.

The same monotonic walk used for the CGST Rules rejects that trailing noise: section
numbers run in order through the Act, so an entry whose number goes backwards is not
a section. Verified on Goa: 169 of the 174 sections recovered.

Usage: python3 split_sgst_acts.py --check
       python3 split_sgst_acts.py
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW_DB = ROOT / "data" / "law" / "law.db"

# The heading runs straight into the section text, so the title is the part before
# the terminating dash. Both em-dash and hyphen occur across the state Acts.
HEADING = re.compile(r"(\d{1,3}[A-Z]?)\.\s+([A-Z][^.]{4,90}?)\s*\.\s*[—–]")
# An "Arrangement of Sections" index lists every section number and title up front.
ARRANGEMENT = re.compile(r"ARRANGEMENT\s+OF\s+SECTIONS", re.I)
# Marginal-note style: the heading is set in the margin, often split across lines
# AFTER the section text ("1. (1) This Act may be called ... ;  Short title, extent
# and commencement."). Detected rather than parsed — see the note in main().
MARGINAL = re.compile(r"^\s*\d{1,3}\.\s*\(1\)", re.M)

# A parse yielding fewer than this many sections for a full Act is not a parse.
MIN_PLAUSIBLE = 100


def classify(text: str, parsed: int) -> str:
    """Which gazette layout this Act uses — they differ enough to need saying."""
    if parsed >= MIN_PLAUSIBLE:
        return "inline heading"
    if ARRANGEMENT.search(text or ""):
        return "arrangement index only"
    if MARGINAL.search(text or ""):
        return "marginal note"
    return "unrecognised"


def _law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def flatten(text: str) -> str:
    """Collapse the blank-line-per-line layout so headings become findable."""
    return re.sub(r"\s+", " ", text or "")


def split_act(text: str) -> list[dict]:
    """Sections in document order, with the amendment-table tail rejected."""
    flat = flatten(text)
    kept: list[tuple[str, str, int, int]] = []
    last = 0
    for m in HEADING.finditer(flat):
        n = int(re.match(r"\d+", m.group(1)).group())
        if n < last:            # the amendment table restarts / jumps backwards
            continue
        if n == 0 or n > 400:   # not a plausible section number
            continue
        kept.append((m.group(1), m.group(2).strip().rstrip("."), m.start(), m.end()))
        last = n
    out = []
    for i, (num, title, _s, e) in enumerate(kept):
        end = kept[i + 1][2] if i + 1 < len(kept) else len(flat)
        out.append({"number": num, "title": title, "text": flat[e:end].strip()})
    return out


def main(check: bool = False) -> None:
    con = sqlite3.connect(LAW_DB)
    con.row_factory = sqlite3.Row
    acts = con.execute(
        "SELECT id, title, body, source_url, pub_date FROM documents"
        " WHERE kind='sgst_act' AND LENGTH(COALESCE(body,'')) > 500 ORDER BY title"
    ).fetchall()
    print(f"state GST Acts held: {len(acts)}")

    law_db = _law_db()
    total_sections = 0
    formats: dict[str, int] = {}
    written = 0
    for a in acts:
        secs = split_act(a["body"])
        fmt = classify(a["body"], len(secs))
        formats[fmt] = formats.get(fmt, 0) + 1
        total_sections += len(secs)
        # GUARD: only write a parse we actually believe. An Act whose text uses a
        # different layout must be reported, not silently stored as a handful of
        # stray "sections" that would look like coverage.
        if len(secs) < MIN_PLAUSIBLE:
            continue
        if check:
            continue
        for s in secs:
            body = (f"Section {s['number']} — {s['title']}\n"
                    f"Act: {a['title']}\n"
                    f"Section number: {s['number']}\n"
                    f"Source: India Code ({a['source_url']})\n\n"
                    f"{s['text']}")
            law_db.upsert_document(con, {
                "source_url": f"{a['source_url']}#section-{s['number']}",
                "kind": "sgst_act_section",
                "title": f"Section {s['number']} — {s['title']}"[:300],
                "number": f"Section {s['number']}",
                "pub_date": a["pub_date"] or "",
                "local_path": "",
                "sha256": hashlib.sha256(body.encode()).hexdigest(),
                "body": body})
            written += 1
        con.commit()

    print(f"\nsections parsed: {total_sections:,} across {len(acts)} Acts")
    print(f"\nGAZETTE LAYOUTS ENCOUNTERED")
    for fmt, n in sorted(formats.items(), key=lambda kv: -kv[1]):
        print(f"  {fmt:<24} {n:>4} Acts")
    print("\nThe state Acts are NOT one format. Only the 'inline heading' layout")
    print("(Goa, UTGST) splits with this pattern. The others need per-state work:")
    print("  marginal note   — heading is set in the margin after the text, often")
    print("                    split across lines; needs column-aware extraction")
    print("  arrangement index — has a clean 'Arrangement of Sections' list that")
    print("                    could serve as a section skeleton")
    print("Acts below the plausibility threshold are skipped, not partially stored.")

    if check:
        print("\n(dry run — nothing written)")
    else:
        n = con.execute("SELECT COUNT(*) FROM documents"
                        " WHERE kind='sgst_act_section'").fetchone()[0]
        print(f"\nsgst_act_section rows held: {n:,}  (from {written:,} parsed)")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    main(check=ap.parse_args().check)
