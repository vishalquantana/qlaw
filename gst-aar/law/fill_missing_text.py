#!/usr/bin/env python3
"""Fill law.db documents whose body is empty, from the local PDF.

Why this exists: some harvesters write the PDF and upsert the row with
`body=""` (harvest_cbic_flat does exactly this). The document is then *held*
but not searchable, and documents_fts carries an empty row. This walks those
rows, extracts the text layer with PyMuPDF, and re-upserts through law_db so
the FTS index stays in sync.

Thin scans (below MIN_CHARS) are left empty and counted for the OCR queue
(ocr_thin.py) rather than being written as garbage.

Idempotent and resumable: rows that already carry a body are skipped.

Usage: python3 fill_missing_text.py            (all empty-body rows)
       python3 fill_missing_text.py --limit 5  (smoke test)
"""
from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

MIN_CHARS = 500


def _load_law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolve(local_path: str) -> Path:
    p = Path(local_path)
    if not p.is_absolute():
        p = ROOT.parent / p
    return p


def main(limit: int = 0) -> None:
    import fitz

    law_db = _load_law_db()
    con = law_db.init_db()
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, source_url, kind, title, number, pub_date, local_path, sha256"
        " FROM documents WHERE TRIM(COALESCE(body,'')) = '' ORDER BY id").fetchall()
    if limit:
        rows = rows[:limit]
    print(f"{len(rows)} documents with an empty body", flush=True)

    filled = thin = missing = 0
    for i, r in enumerate(rows, 1):
        p = _resolve(r["local_path"])
        if not r["local_path"] or not p.exists():
            missing += 1
            continue
        try:
            text = "\n\n".join(pg.get_text() for pg in fitz.open(p)).strip()
        except Exception as e:
            print(f"  skip {p.name}: {type(e).__name__}", file=sys.stderr)
            continue
        if len(text) < MIN_CHARS:
            thin += 1
            continue
        law_db.upsert_document(con, {
            "source_url": r["source_url"], "kind": r["kind"], "title": r["title"],
            "number": r["number"], "pub_date": r["pub_date"],
            "local_path": r["local_path"], "sha256": r["sha256"], "body": text})
        filled += 1
        if i % 100 == 0:
            print(f"  [{i}/{len(rows)}] filled={filled} thin={thin}", flush=True)

    print(f"done: filled={filled} thin={thin} (OCR queue) missing={missing}")
    n_body = con.execute(
        "SELECT COUNT(*) FROM documents WHERE TRIM(COALESCE(body,'')) <> ''").fetchone()[0]
    n_all = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"documents with body: {n_body}/{n_all}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    main(**vars(ap.parse_args()))
