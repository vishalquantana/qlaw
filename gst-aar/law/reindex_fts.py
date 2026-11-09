#!/usr/bin/env python3
"""Re-sync documents_fts from documents.

The FTS index can drift from the documents table whenever a writer updates
`documents.body` with a bare UPDATE instead of going through
`law_db.upsert_document`. The FTS row still exists, so the document is held and
readable, but `MATCH` returns nothing for its text - it is silently
unsearchable. An earlier ingest path and `ocr_thin.py` both did this.

`law_db.upsert_document` keeps the two in step, so this is a repair for drift
that already happened, not part of the normal write path.

Usage: python3 reindex_fts.py --check   (report drift only, changes nothing)
       python3 reindex_fts.py           (re-sync every row)
"""
from __future__ import annotations

import argparse
import importlib.util
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
LAW_DB = HERE.parent / "data" / "law" / "law.db"


def reindex(con: sqlite3.Connection) -> int:
    """Rewrite every FTS row from documents. Returns rows rewritten."""
    rows = con.execute("SELECT id, title, number, body FROM documents").fetchall()
    con.executemany(
        "INSERT OR REPLACE INTO documents_fts(rowid, title, number, body)"
        " VALUES (?,?,?,?)",
        [(i, t or "", n or "", b or "") for i, t, n, b in rows])
    con.commit()
    return len(rows)


def drift(con: sqlite3.Connection) -> tuple[int, int]:
    """(documents with body, of those, how many have an empty FTS body)."""
    has_body = con.execute(
        "SELECT COUNT(*) FROM documents WHERE TRIM(COALESCE(body,'')) <> ''"
    ).fetchone()[0]
    stale = con.execute(
        "SELECT COUNT(*) FROM documents d JOIN documents_fts f ON f.rowid = d.id"
        " WHERE TRIM(COALESCE(d.body,'')) <> '' AND TRIM(COALESCE(f.body,'')) = ''"
    ).fetchone()[0]
    return has_body, stale


def main(check: bool = False) -> None:
    con = sqlite3.connect(LAW_DB)
    try:
        has_body, stale = drift(con)
        print(f"documents with body: {has_body}, unsearchable (FTS body empty): {stale}")
        if check:
            return
        if not stale:
            print("nothing to do")
            return
        n = reindex(con)
        _, after = drift(con)
        print(f"reindexed {n} rows; unsearchable now: {after}")
    finally:
        con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    main(check=args.check)
