#!/usr/bin/env python3
"""Harvest the CGST Rules, 2017 text from the CBIC's own consolidated PDF.

Why this matters: the CBIC API gave us the rule *structure* (1,294 rule-section
rows) but no wording — and those rows span many rule sets with no parent recorded,
so "Rule 1" appears 72 times. The CBIC publishes the consolidated CGST Rules as a
single PDF, which is both authoritative and complete.

Splitting it is the only interesting part. A plain heading regex picks up table
rows inside the rules themselves (Rule 7 contains a table numbered 1, 2, 3), which
inflate the count to ~1,100 "headings" for 162 rules. Rule numbering is monotonic
through the document, so walking the loose matches in order and keeping only those
whose number does not go backwards rejects every table row — leaving exactly 162
rules with no gaps. Verified: rules 1..162 all present.

Usage: python3 harvest_cgst_rules.py [--pdf /path/to.pdf]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
STAGE = ROOT / "data" / "law" / "staging" / "cbic-rules"
PDF = STAGE / "cgst-rules-2017.pdf"
URL = "https://cbic-gst.gov.in/pdf/cgst-rules-01july2017.pdf"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

HEADING = re.compile(r"^[ \t]*(\d{1,3}[A-Z]?)\.\s+([A-Z][^\n]{4,120})$", re.M)

try:
    import _throttle as _thr
except ImportError:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", HERE / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)


def _law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch_pdf(dest: Path = PDF) -> Path:
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"using cached {dest}")
        return dest
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    _thr.wait(URL)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(URL, headers=UA), timeout=180) as r:
            blob = r.read()
        _thr.on_success(URL)
    except Exception as e:
        _thr.on_error(URL, e)
        raise
    dest.write_bytes(blob)
    print(f"downloaded {len(blob):,} bytes -> {dest}")
    return dest


def split_rules(text: str) -> list[dict]:
    """Return the rules in document order, rejecting table rows inside them.

    A rule's text usually begins on the SAME line as its heading
    ("1. Short title and Commencement.- (1) These rules may be called ..."), so the
    part of the heading line after the ".-" has to be carried into the body —
    otherwise every rule loses its opening sentence.
    """
    kept: list[tuple[str, str, int, int, str]] = []
    last = 0
    for m in HEADING.finditer(text):
        num = m.group(1)
        n = int(re.match(r"\d+", num).group())
        if n < last:            # a table row restarting at 1 — not a rule heading
            continue
        parts = re.split(r"\.\s*-", m.group(2), maxsplit=1)
        title = parts[0].strip().rstrip(".").strip()
        inline = parts[1].strip() if len(parts) > 1 else ""
        kept.append((num, title or m.group(2).strip(), m.start(), m.end(), inline))
        last = n
    out = []
    for i, (num, title, _s, e, inline) in enumerate(kept):
        end = kept[i + 1][2] if i + 1 < len(kept) else len(text)
        body = "\n".join(p for p in (inline, text[e:end].strip()) if p).strip()
        out.append({"number": num, "title": title, "text": body})
    return out


def main(pdf_path: str = "") -> None:
    src = Path(pdf_path) if pdf_path else fetch_pdf()
    import fitz  # PyMuPDF

    doc = fitz.open(src)
    text = "\n".join(p.get_text() for p in doc)
    print(f"{len(doc)} pages, {len(text):,} chars")

    rules = split_rules(text)
    if not rules:
        sys.exit("no rules found — check the heading pattern")
    nums = [r["number"] for r in rules]
    print(f"rules parsed: {len(rules)}  first={nums[0]} last={nums[-1]}")

    law_db = _law_db()
    con = law_db.init_db()
    # drop anything a previous run wrote under the bare PDF url, and any prior
    # attempt at these rules, so a re-run is idempotent
    con.execute("DELETE FROM documents WHERE kind='cgst_rule'")
    con.commit()

    added = 0
    for r in rules:
        # `documents.source_url` is the unique key, so each rule needs its own.
        # The fragment keeps it a resolvable .gov.in URL while disambiguating.
        rule_url = f"{URL}#rule-{r['number']}"
        body = (f"Rule {r['number']} — {r['title']}\n"
                f"Rule set: Central Goods and Services Tax Rules, 2017\n"
                f"Source: CBIC consolidated rules ({URL})\n\n"
                f"{r['text']}")
        law_db.upsert_document(con, {
            "source_url": rule_url, "kind": "cgst_rule",
            "title": f"Rule {r['number']} — {r['title']}"[:300],
            "number": r["number"], "pub_date": "2017-06-19",
            "local_path": str(src),
            "sha256": hashlib.sha256(body.encode()).hexdigest(), "body": body})
        added += 1
    con.commit()

    n = con.execute("SELECT COUNT(*) FROM documents WHERE kind='cgst_rule'").fetchone()[0]
    substantial = con.execute(
        "SELECT COUNT(*) FROM documents WHERE kind='cgst_rule'"
        " AND LENGTH(body) > 300").fetchone()[0]
    print(f"\ncgst_rule rows: {n}  (with substantial text: {substantial})")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="", help="use a local PDF instead of downloading")
    args = ap.parse_args()
    main(pdf_path=args.pdf)
