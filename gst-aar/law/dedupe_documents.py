#!/usr/bin/env python3
"""Flag documents that duplicate another document's text, and record the link.

Why they exist: some state portals publish ONE consolidated G.O. covering many
notifications, and every notification row links to that same document. The
harvester correctly recorded a row per notification, but the ingest then stored
the same extracted text once per row — so the corpus appeared to hold N documents
where it holds one, referenced N times. Telangana's rate compilation is the
largest case (36 rows, one file).

This does not delete anything. It:
  * picks a canonical row per identical body (the lowest id),
  * records each duplicate's own title/number as a citation on the canonical row,
    so the notification identities are not lost,
  * tags the duplicate `duplicate-of:<canonical id>` in law_tags.

Corrected counts then exclude tagged rows:
    SELECT COUNT(*) FROM documents d
    WHERE NOT EXISTS (SELECT 1 FROM law_tags t
                      WHERE t.doc_id = d.id AND t.tag LIKE 'duplicate-of:%');

Usage: python3 dedupe_documents.py --check
       python3 dedupe_documents.py
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sqlite3
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW_DB = ROOT / "data" / "law" / "law.db"


def _law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def clusters(con: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    by_hash: dict[str, list] = defaultdict(list)
    con.row_factory = sqlite3.Row
    for r in con.execute(
            "SELECT id, kind, title, number, local_path, body FROM documents"
            " WHERE TRIM(COALESCE(body,'')) <> ''"):
        by_hash[hashlib.sha256(r["body"].encode()).hexdigest()].append(r)
    return {h: v for h, v in by_hash.items() if len(v) > 1}


def main(check: bool = False) -> None:
    law_db = _law_db()
    con = law_db.init_db()
    con.executescript("""CREATE TABLE IF NOT EXISTS law_tags (
        id INTEGER PRIMARY KEY,
        doc_id INTEGER NOT NULL REFERENCES documents(id),
        tag TEXT NOT NULL, UNIQUE(doc_id, tag));
        CREATE TABLE IF NOT EXISTS law_citations (
        id INTEGER PRIMARY KEY,
        doc_id INTEGER NOT NULL REFERENCES documents(id),
        cite_type TEXT NOT NULL,
        identifier TEXT NOT NULL,
        UNIQUE(doc_id, cite_type, identifier));""")

    cl = clusters(con)
    redundant = sum(len(v) - 1 for v in cl.values())
    total = con.execute(
        "SELECT COUNT(*) FROM documents WHERE TRIM(COALESCE(body,''))<>''").fetchone()[0]
    print(f"documents with body        : {total:,}")
    print(f"clusters of identical text : {len(cl):,}")
    print(f"redundant rows             : {redundant:,}")
    if check:
        return

    tagged = cited = 0
    for h, rows in cl.items():
        rows = sorted(rows, key=lambda r: r["id"])
        canonical = rows[0]
        for dup in rows[1:]:
            # keep the duplicate's own identity as a citation on the canonical row
            ident = (dup["title"] or dup["number"] or f"document {dup['id']}").strip()
            con.execute(
                "INSERT OR IGNORE INTO law_citations (doc_id, cite_type, identifier)"
                " VALUES (?, 'notification_ref', ?)", (canonical["id"], ident[:300]))
            cited += 1
            con.execute("INSERT OR IGNORE INTO law_tags (doc_id, tag) VALUES (?,?)",
                        (dup["id"], f"duplicate-of:{canonical['id']}"))
            tagged += 1
    con.commit()

    unique = con.execute(
        "SELECT COUNT(*) FROM documents d WHERE NOT EXISTS (SELECT 1 FROM law_tags t"
        " WHERE t.doc_id = d.id AND t.tag LIKE 'duplicate-of:%')").fetchone()[0]
    print(f"\ntagged {tagged} duplicates, added {cited} notification_ref citations")
    print(f"documents excluding duplicates: {unique:,} (was {total + (con.execute('SELECT COUNT(*) FROM documents').fetchone()[0] - total):,} total rows)")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    main(check=args.check)
