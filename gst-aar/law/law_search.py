#!/usr/bin/env python3
"""CLI over law.db: document search, and HSN / SAC rate lookup.

    python3 law_search.py "input tax credit"          # full-text document search
    python3 law_search.py "e-invoicing" --kind circular
    python3 law_search.py --rate 0401                 # rate for an HSN/SAC code
    python3 law_search.py --rate-search milk          # find codes by description

The rate tables are built by `harvest_gst_rates.py` from the CBIC rate schedule:
`rate_facts` holds one row per published schedule line, `rate_codes` maps each
individual code to its line.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

sys.path.insert(0, "tests")
from gst_aar_law_shim import law_db

DB = law_db.LAW_DB


def show_documents(con: sqlite3.Connection, query: str, kind: str, limit: int) -> int:
    rows = law_db.search(con, query, limit * 2 if kind else limit)
    n = 0
    for r in rows:
        if kind and r["kind"] != kind:
            continue
        print(f"#{r['id']} [{r['pub_date'] or '????-??-??'}] [{r['kind']}] "
              f"{r['title']} ({r['number']})")
        print(f"    {r['source_url']}")
        n += 1
        if n >= limit:
            break
    if not n:
        print("  no matches")
    return n


def show_rate(con: sqlite3.Connection, code: str, limit: int) -> int:
    rows = con.execute("""
        SELECT f.kind, f.schedule, f.sr_no, f.hsn_sac, f.description,
               f.cgst_rate, f.sgst_rate, f.igst_rate, f.cess, f.condition, f.source_url
        FROM rate_codes c JOIN rate_facts f ON f.id = c.fact_id
        WHERE c.code = ? ORDER BY f.kind, f.schedule, f.sr_no""", (code,)).fetchall()
    if not rows:
        print(f"  no rate line carries code {code}")
        return 0
    print(f"  {len(rows)} rate line(s) for code {code}\n")
    for (kind, sch, sr, hsn, desc, cgst, sgst, igst, cess, cond, src) in rows[:limit]:
        head = f"{kind}" + (f" · Schedule {sch}" if sch else "")
        print(f"  [{head} · S.No {sr}] {hsn}")
        print(f"      {desc[:150]}")
        print(f"      CGST {cgst or '—'}   SGST/UTGST {sgst or '—'}   "
              f"IGST {igst or '—'}   Cess {cess or '—'}")
        if cond:
            print(f"      condition: {cond[:140]}")
    print(f"\n  source: {rows[0][10]}")
    return len(rows)


def show_rate_search(con: sqlite3.Connection, text: str, limit: int) -> int:
    rows = con.execute("""
        SELECT kind, schedule, sr_no, hsn_sac, description, cgst_rate, igst_rate
        FROM rate_facts WHERE description LIKE ?
        ORDER BY kind, schedule, sr_no LIMIT ?""", (f"%{text}%", limit)).fetchall()
    if not rows:
        print(f"  no rate line mentions {text!r}")
        return 0
    print(f"  {len(rows)} rate line(s) matching {text!r}\n")
    for kind, sch, sr, hsn, desc, cgst, igst in rows:
        head = f"{kind}" + (f" Sch {sch}" if sch else "")
        print(f"  [{head} #{sr}] {hsn[:34]:36s} CGST {cgst or '—':>6}  "
              f"IGST {igst or '—':>6}  {desc[:70]}")
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--rate", metavar="HSN_SAC",
                    help="look up the rate for one commodity/service code")
    ap.add_argument("--rate-search", metavar="TEXT",
                    help="find rate lines by description")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if args.rate:
        show_rate(con, args.rate.strip(), args.limit)
    elif args.rate_search:
        show_rate_search(con, args.rate_search, args.limit)
    elif args.query:
        show_documents(con, args.query, args.kind, args.limit)
    else:
        ap.error("give a query, or --rate / --rate-search")
    con.close()


if __name__ == "__main__":
    main()
