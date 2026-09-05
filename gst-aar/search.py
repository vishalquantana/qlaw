#!/usr/bin/env python3
"""Search the local AAR/AAAR rulings database.

Examples:
  python3 search.py "hsn 9984"                  # full-text search
  python3 search.py "e-invoicing" --state Karnataka --limit 20
  python3 search.py --state Gujarat --date-from 2025-01-01
  python3 search.py "job work" --full           # show extracted text excerpts
"""
import argparse
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data" / "aar.db"

SELECT_COLS = (
    "r.id, r.sr_no, r.applicant, r.state, r.order_no, r.order_date, r.category,"
    " r.brief, r.pdf_url, r.extraction_status"
)


def search(query: str | None, state: str | None, date_from: str | None,
           date_to: str | None, limit: int, full: bool):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    where, params = [], []
    fts_join = ""

    if query:
        fts_join = "JOIN rulings_fts f ON f.rowid = r.id JOIN (SELECT rowid, rank FROM rulings_fts WHERE rulings_fts MATCH ? LIMIT -1) fr ON fr.rowid = r.id"
        # quote each term so hyphens/commas don't parse as FTS column syntax
        fts_query = " ".join(f'"{t}"' for t in query.split() if t)
        params.append(fts_query)
    if state:
        where.append("r.state LIKE ? COLLATE NOCASE")
        params.append(f"%{state}%")
    if date_from:
        where.append("r.order_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("r.order_date <= ?")
        params.append(date_to)

    sql = f"SELECT {SELECT_COLS}{', fr.rank AS score' if query else ''} FROM rulings r {fts_join}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if query:
        sql += " ORDER BY fr.rank"
    else:
        sql += " ORDER BY r.order_date DESC, r.id DESC"
    sql += " LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    for r in rows:
        print(f"#{r['id']} [{r['order_date'] or '????-??-??'}] {r['state']}: {r['applicant']}")
        print(f"    {r['order_no']}   ({r['category']})   status={r['extraction_status']}")
        brief = (r["brief"] or "")[:300]
        print(f"    brief: {brief}{'…' if len(brief) > 300 else ''}")
        print(f"    pdf: {r['pdf_url']}")
        if full:
            txt = con.execute(
                "SELECT txt_file FROM rulings WHERE id = ?", (r["id"],)
            ).fetchone()
            if txt and txt["txt_file"]:
                body = (Path(__file__).parent / txt["txt_file"]).read_text(errors="replace")
                ql = [t for t in (query or "").split() if len(t) > 2]
                for term in ql[:3]:
                    idx = body.lower().find(term.lower())
                    if idx >= 0:
                        print(f"    …{body[max(0, idx-100):idx+250]}…".replace("\n", " "))
                        break
        print()
    if not rows:
        print("no results")
    con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="*", help="full-text query")
    ap.add_argument("--state")
    ap.add_argument("--date-from")
    ap.add_argument("--date-to")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--full", action="store_true", help="show text excerpts")
    args = ap.parse_args()
    search(" ".join(args.query) or None, args.state, args.date_from, args.date_to,
           args.limit, args.full)


if __name__ == "__main__":
    main()
