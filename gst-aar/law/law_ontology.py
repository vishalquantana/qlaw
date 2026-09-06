#!/usr/bin/env python3
"""Structured ontology over law.db documents (mirrors ontology.sql for AARs).

Tables: law_subjects (what the doc is about), law_citations (numbers it
cites), law_tags (sector/topic tags). Pass 1 (this script, regex, seconds):
HSN/SAC codes, notification & circular numbers, section/rule citations,
GSTINs, effective dates. Pass 2 (LLM, separate): subject/outcome/sector.

Usage: python3 law_ontology.py --apply-pass1   (idempotent, resumable)
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys

sys.path.insert(0, "tests")
from gst_aar_law_shim import law_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS law_subjects (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    kind TEXT DEFAULT '',
    label TEXT DEFAULT '',
    description TEXT DEFAULT '',
    hsn_sac TEXT DEFAULT '',
    rate_proposed TEXT DEFAULT '',
    rate_held TEXT DEFAULT '',
    outcome TEXT DEFAULT '',
    effective_date TEXT DEFAULT '',
    UNIQUE(doc_id, label)
);
CREATE TABLE IF NOT EXISTS law_citations (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    cite_type TEXT NOT NULL,
    identifier TEXT NOT NULL,
    UNIQUE(doc_id, cite_type, identifier)
);
CREATE TABLE IF NOT EXISTS law_tags (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    tag TEXT NOT NULL,
    UNIQUE(doc_id, tag)
);
"""

HSN_RE = re.compile(r'\b(\d{4}[ -]?\d{0,4})\b')
NOTIF_RE = re.compile(r'\b(?:Notification\s+)?No\.?\s*(\d{1,3}/\d{4})\s*[-–]?\s*(Central Tax|Integrated Tax|UT Tax|Compensation Cess)?(?:\s*\(Rate\))?', re.I)
CIRC_RE = re.compile(r'\b(?:Circular\s+No\.?\s*)?(\d{1,3}/\d{2,4}/\d{4})\s*[-–]?\s*GST\b', re.I)
SECT_RE = re.compile(r'\b[Ss]ection\s+(\d{1,3}[A-Z]?)\s+(?:of\s+the\s+)?(CGST|IGST|SGST|UTGST|Cess)?\s*(Act)?', re.I)
RULE_RE = re.compile(r'\b[Rr]ule\s+(\d{1,3}[A-Z]?)\b.{0,30}(CGST|GST)?\s*[Rr]ules?', re.I)
GSTIN_RE = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b')
EFF_RE = re.compile(r'(?:with effect from|w\.e\.f\.|effective from|shall come into force on)\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s*,?\s*\d{4}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})', re.I)

SECTOR_KEYWORDS = {
    'e-invoicing': 'e-invoicing', 'qr code': 'e-invoicing', 'refund': 'refunds',
    'input tax credit': 'ITC', 'ITC': 'ITC', 'revocation': 'registration',
    'cancellation of registration': 'registration', 'rate': 'rates',
    'exempt': 'exemption', 'anti-profiteering': 'anti-profiteering',
    'place of supply': 'place-of-supply', 'job work': 'job-work',
    'composition': 'composition', 'appeal': 'appeals', 'advance ruling': 'AAR',
}


def pass1_doc(con: sqlite3.Connection, doc_id: int, body: str) -> dict:
    counts = {'subjects': 0, 'citations': 0, 'tags': 0}
    seen_cites = set()

    def cite(ctype: str, ident: str):
        ident = ' '.join(ident.split())
        if not ident or (ctype, ident) in seen_cites:
            return
        seen_cites.add((ctype, ident))
        con.execute("INSERT OR IGNORE INTO law_citations (doc_id, cite_type, identifier)"
                    " VALUES (?,?,?)", (doc_id, ctype, ident))
        counts['citations'] += 1

    hsns = sorted({h.replace(' ', '').replace('-', '') for h in HSN_RE.findall(body)
                   if 4 <= len(h.replace(' ', '').replace('-', '')) <= 8})
    for h in hsns[:20]:
        cite('hsn_sac', h)
    for num, cat in NOTIF_RE.findall(body)[:20]:
        cite('notification', f"{num} {cat or ''}".strip())
    for num in CIRC_RE.findall(body)[:20]:
        cite('circular', num)
    for sec, tax, _ in SECT_RE.findall(body)[:30]:
        cite('section', f"{tax + ' ' if tax else ''}s.{sec}")
    for rule, _ in RULE_RE.findall(body)[:20]:
        cite('rule', f"rule {rule}")
    for g in set(GSTIN_RE.findall(body)):
        cite('gstin', g)
    effs = EFF_RE.findall(body)[:5]
    low = body.lower()
    for kw, tag in SECTOR_KEYWORDS.items():
        if kw.lower() in low:
            con.execute("INSERT OR IGNORE INTO law_tags (doc_id, tag) VALUES (?,?)",
                        (doc_id, tag))
            counts['tags'] += 1
    if effs or hsns:
        con.execute("INSERT OR IGNORE INTO law_subjects"
                    " (doc_id, kind, label, hsn_sac, effective_date)"
                    " VALUES (?,?,?,?,?)",
                    (doc_id, '', (body.split('\n')[0] or '')[:200],
                     ','.join(hsns[:10]), effs[0] if effs else ''))
        counts['subjects'] += 1
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply-pass1', action='store_true', required=True)
    ap.parse_args()
    con = law_db.init_db()
    con.executescript(SCHEMA)
    rows = con.execute("SELECT id, body FROM documents WHERE body != '' ORDER BY id").fetchall()
    total = {'subjects': 0, 'citations': 0, 'tags': 0}
    for doc_id, body in rows:
        for k, v in pass1_doc(con, doc_id, body).items():
            total[k] += v
    con.commit()
    print(f"pass1 over {len(rows)} docs: {total}")


if __name__ == '__main__':
    main()
