#!/usr/bin/env python3
"""Export the document inventory: one row per document ever ingested, with the
ORIGINAL source URL of the PDF it came from.

Outputs:
  data/inventory.csv  - human-readable, survives restarts, diffable
  data/inventory.jsonl - machine-readable, same fields

Rule (standing): every document in this pipeline must be traceable to its
original publisher URL. No document without a source URL ships downstream.
"""
import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "aar.db"

FIELDS = [
    "doc_key",        # stable id: state_dir/filename
    "state",
    "applicant",
    "order_no",
    "order_date",
    "category",
    "brief",          # subject/questions ruled on (from listing)
    "source_url",     # ORIGINAL publisher URL of the PDF (provenance)
    "pdf_file",       # local copy, relative to gst-aar/
    "pdf_size_bytes",
    "pdf_downloaded_at",
    "txt_file",
    "text_chars",
    "pages",
    "ocr_pages",
    "status",         # not_downloaded | ok | cached | ocr_failed | error_*
]


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM rulings"
    ).fetchall()

    # ocr page counts live in extract_status.jsonl keyed "<StateDir>/<file>.pdf"
    ocr_pages = {}
    status_file = DATA / "extract_status.jsonl"
    if status_file.exists():
        with status_file.open() as f:
            for line in f:
                st = json.loads(line)
                ocr_pages[st.get("pdf", "")] = st.get("ocr_pages", "")

    out_csv = DATA / "inventory.csv"
    out_jsonl = DATA / "inventory.jsonl"
    n = 0
    with out_csv.open("w", newline="", encoding="utf-8") as fc, out_jsonl.open("w", encoding="utf-8") as fj:
        w = csv.DictWriter(fc, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            pdf_file = r["pdf_file"]
            if pdf_file and Path(pdf_file).exists():
                p = Path(pdf_file)
                pdf_size = p.stat().st_size
                pdf_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))
            else:
                pdf_size, pdf_at = "", ""
            rec = {
                "doc_key": f"{(r['state'] or 'unknown').strip().replace(' ', '_')}/{(r['pdf_url'] or '').rsplit('/', 1)[-1]}",
                "state": r["state"],
                "applicant": r["applicant"],
                "order_no": r["order_no"],
                "order_date": r["order_date"],
                "category": r["category"],
                "brief": (r["brief"] or "")[:500],
                "source_url": r["pdf_url"],
                "pdf_file": str(Path(pdf_file).relative_to(ROOT)) if pdf_file and Path(pdf_file).exists() else "",
                "pdf_size_bytes": pdf_size,
                "pdf_downloaded_at": pdf_at,
                "txt_file": r["txt_file"] or "",
                "text_chars": r["chars"] or 0,
                "pages": r["pages"] or "",
                "ocr_pages": ocr_pages.get(f"{(r['state'] or 'unknown').strip().replace(' ', '_').replace('/', '-')}/{(r['pdf_url'] or '').rsplit('/', 1)[-1]}", ""),
                "status": r["extraction_status"],
            }
            w.writerow(rec)
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    con.close()
    print(f"inventory: {n} documents -> {out_csv} and {out_jsonl}")


if __name__ == "__main__":
    main()
