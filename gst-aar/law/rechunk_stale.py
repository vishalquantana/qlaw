#!/usr/bin/env python3
"""Drop chunks that no longer cover their document's text, so they can be rebuilt.

Why this is needed: `embed_law.py` chunks whatever `documents.body` holds at the
time it runs, and skips any (doc_id, chunk_index) that already exists. When a
body is later *enriched* — as happened when the CBIC section rows received their
India Code wording — the existing chunks still hold the old, short text and are
never revisited. The document reads correctly but its vectors point at a stub:
651 sections were carrying 80 KB of chunk text against 1.25 MB of actual body,
the worst being a 31,385-character section represented by a 98-character chunk.

Detection is by coverage: if the chunks for a document hold less than
`--min-ratio` of its body, they are treated as stale. Re-run `embed_law.py`
afterwards to rebuild them.

Usage: python3 rechunk_stale.py --check
       python3 rechunk_stale.py            (deletes the stale chunks)
       python3 rechunk_stale.py --min-ratio 0.8
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
LAW_DB = HERE.parent / "data" / "law" / "law.db"


def stale_docs(con: sqlite3.Connection, min_ratio: float) -> list[tuple]:
    rows = con.execute("""
        SELECT d.id, d.kind, LENGTH(COALESCE(d.body,'')) AS blen,
               SUM(LENGTH(c.text)) AS clen, COUNT(c.chunk_id) AS n
        FROM documents d JOIN law_chunks c ON c.doc_id = d.id
        GROUP BY d.id""").fetchall()
    return [r for r in rows if r[2] and r[3] is not None and r[3] < min_ratio * r[2]]


def main(check: bool = False, min_ratio: float = 0.5) -> None:
    con = sqlite3.connect(LAW_DB)
    stale = stale_docs(con, min_ratio)
    total_docs = con.execute(
        "SELECT COUNT(DISTINCT doc_id) FROM law_chunks").fetchone()[0]
    print(f"documents with chunks                 : {total_docs:,}")
    print(f"stale (chunks cover <{min_ratio:.0%} of body) : {len(stale):,}")
    if stale:
        kinds: dict[str, int] = {}
        for r in stale:
            kinds[r[1]] = kinds.get(r[1], 0) + 1
        print("  by kind:", dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:6]))
        print(f"  chunk text {sum(r[3] for r in stale):,} chars "
              f"vs {sum(r[2] for r in stale):,} chars of body")
    if check or not stale:
        if not stale:
            print("nothing to do")
        con.close()
        return

    ids = [r[0] for r in stale]
    deleted = 0
    for i in range(0, len(ids), 500):
        batch = ids[i:i + 500]
        q = ",".join("?" * len(batch))
        cur = con.execute(f"DELETE FROM law_chunks WHERE doc_id IN ({q})", batch)
        deleted += cur.rowcount
    con.commit()
    left = con.execute("SELECT COUNT(*) FROM law_chunks").fetchone()[0]
    print(f"\ndeleted {deleted:,} stale chunks; {left:,} remain")
    print("now run: python3 gst-aar/law/embed_law.py")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-ratio", type=float, default=0.5)
    args = ap.parse_args()
    main(check=args.check, min_ratio=args.min_ratio)
