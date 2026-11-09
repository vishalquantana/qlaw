#!/usr/bin/env python3
"""One-shot status of the GST law corpus.

    python3 gst-aar/law/status.py

Counts exclude rows tagged `duplicate-of:*` (see dedupe_documents.py).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW_DB = ROOT / "data" / "law" / "law.db"
AAR_DB = ROOT / "data" / "aar.db"

ND = ("NOT EXISTS (SELECT 1 FROM law_tags t WHERE t.doc_id = d.id"
      " AND t.tag LIKE 'duplicate-of:%')")
BODY = "TRIM(COALESCE(d.body,'')) <> ''"

LAYER_SQL = f"""
SELECT CASE
         WHEN d.kind = 'sgst_act' THEN 'State GST Acts'
         WHEN d.kind LIKE '%\\_notification' ESCAPE '\\' THEN 'State GST notifications'
         WHEN d.kind LIKE 'cbic\\_%' ESCAPE '\\' THEN 'Central Acts/Rules/sections'
         WHEN d.kind IN ('notification','circular') THEN 'Central notif + circular'
         WHEN d.kind LIKE 'council%' THEN 'Council minutes/papers'
         WHEN d.kind IN ('bill','act') THEN 'Bills + Acts'
         ELSE 'Other' END AS layer, COUNT(*) AS n
FROM documents d WHERE {ND} GROUP BY layer ORDER BY n DESC"""


def main() -> None:
    con = sqlite3.connect(LAW_DB)
    con.row_factory = sqlite3.Row

    def one(sql: str, *args):
        return con.execute(sql, args).fetchone()[0]

    def flag(ok: bool, bad: str = "** FIX **") -> str:
        return "OK" if ok else bad

    print("=" * 60)
    print("GST law corpus — status")
    print("=" * 60)

    print("\nDOCUMENTS")
    rows_ = one("SELECT COUNT(*) FROM documents")
    uniq = one(f"SELECT COUNT(*) FROM documents d WHERE {ND}")
    withbody = one(f"SELECT COUNT(*) FROM documents d WHERE {ND} AND {BODY}")
    drift = one("SELECT COUNT(*) FROM documents d JOIN documents_fts f ON f.rowid = d.id"
                f" WHERE {BODY} AND TRIM(COALESCE(f.body,'')) = ''")
    print(f"  rows in law.db              {rows_:>9,}")
    print(f"  excluding duplicates        {uniq:>9,}")
    print(f"  with extracted text         {withbody:>9,}")
    print(f"  FTS index drift             {drift:>9,}   {flag(drift == 0)}")

    print("\nBY LAYER (excluding duplicates)")
    for r in con.execute(LAYER_SQL):
        print(f"  {r['layer']:<28} {r['n']:>9,}")

    print("\nSTATE COVERAGE")
    tagged = one("SELECT COUNT(DISTINCT doc_id) FROM law_tags WHERE tag LIKE ?", "state:%")
    nstates = one("SELECT COUNT(DISTINCT tag) FROM law_tags WHERE tag LIKE ?", "state:%")
    print(f"  documents with a state tag  {tagged:>9,}")
    print(f"  states/UTs represented      {nstates:>9,}")

    print("\nSTATUTE TEXT")
    acts = one("SELECT COUNT(*) FROM documents WHERE kind = ?", "sgst_act")
    acts_txt = one("SELECT COUNT(*) FROM documents WHERE kind = ?"
                   " AND LENGTH(COALESCE(body,'')) > 500", "sgst_act")
    tot = one("SELECT COUNT(*) FROM documents WHERE kind = ?", "cbic_act_section")
    txt = one("SELECT COUNT(*) FROM documents WHERE kind = ?"
              " AND body LIKE ?", "cbic_act_section", "%Text source: India Code%")
    print(f"  SGST Acts                   {acts:>9,}")
    print(f"  … with full text            {acts_txt:>9,}")
    print(f"  central sections w/ wording {txt:>9,} / {tot:,}")

    print("\nRATE REFERENCE")
    print(f"  rate lines                  {one('SELECT COUNT(*) FROM rate_facts'):>9,}")
    print(f"  distinct HSN/SAC codes      {one('SELECT COUNT(DISTINCT code) FROM rate_codes'):>9,}")

    print("\nSEMANTIC INDEX")
    chunks = one("SELECT COUNT(*) FROM law_chunks")
    docs_c = one("SELECT COUNT(DISTINCT doc_id) FROM law_chunks")
    need = one("SELECT COUNT(*) FROM documents d"
               " WHERE LENGTH(TRIM(COALESCE(d.body,''))) > 80"
               " AND NOT EXISTS (SELECT 1 FROM law_chunks c WHERE c.doc_id = d.id)")
    cover = con.execute("""
        SELECT d.id, LENGTH(d.body) AS b, SUM(LENGTH(c.text)) AS t
        FROM documents d JOIN law_chunks c ON c.doc_id = d.id GROUP BY d.id""").fetchall()
    stale = sum(1 for r in cover if r["b"] and r["t"] and r["t"] < 0.5 * r["b"])
    print(f"  chunks                      {chunks:>9,}")
    print(f"  documents with chunks       {docs_c:>9,}")
    print(f"  documents needing chunks    {need:>9,}   {flag(need == 0, '** RUN embed_law **')}")
    print(f"  stale chunks (<50% cover)   {stale:>9,}   {flag(stale == 0, '** RUN rechunk_stale **')}")

    rulings = 0
    print("\nADVANCE RULINGS")
    if AAR_DB.exists():
        a = sqlite3.connect(AAR_DB)
        aq = lambda s: a.execute(s).fetchone()[0]  # noqa: E731
        rulings = aq("SELECT COUNT(*) FROM rulings")
        ont = aq("SELECT COUNT(*) FROM rulings WHERE ontology_extracted = 1")
        qs = aq("SELECT COUNT(DISTINCT ruling_id) FROM ruling_questions")
        print(f"  rulings                     {rulings:>9,}")
        print(f"  … ontology extracted        {ont:>9,}   ({100 * ont // max(rulings, 1)}%)")
        print(f"  … with questions            {qs:>9,}   ({100 * qs // max(rulings, 1)}%)")
        a.close()
    else:
        print("  aar.db not found")

    print("\nTOTAL")
    print(f"  law.db {uniq:,} + AAR {rulings:,} = {uniq + rulings:,}")
    con.close()


if __name__ == "__main__":
    main()
