#!/usr/bin/env python3
"""CLI search over law.db (mirrors gst-aar/search.py output style)."""
import argparse
import sqlite3
import sys

sys.path.insert(0, "tests")
from gst_aar_law_shim import law_db

DB = law_db.LAW_DB


def main(query: str, kind: str = "", limit: int = 10):
    con = sqlite3.connect(DB)
    rows = law_db.search(con, query, limit * 2 if kind else limit)
    n = 0
    for r in rows:
        if kind and r["kind"] != kind:
            continue
        print(f"#{r['id']} [{r['pub_date'] or '????-??-??'}] [{r['kind']}] {r['title']} ({r['number']})")
        print(f"    {r['source_url']}")
        n += 1
        if n >= limit:
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--kind", default="")
    ap.add_argument("--limit", type=int, default=10)
    main(**vars(ap.parse_args()))
