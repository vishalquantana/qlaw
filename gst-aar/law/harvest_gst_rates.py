#!/usr/bin/env python3
"""Harvest the CBIC GST rate schedule into a structured HSN / SAC rate reference.

Source: `cbic-gst.gov.in/gst-goods-services-rates.html` — the official CBIC rate
page. Note the **English page's tables are empty** (the CSS targets `#goods_table`
and `#service_table` but no rows are served); the **Hindi mirror carries the data**,
which is the same pattern the notification listings already showed.

Two published tables:
  goods_table    Schedules | S. No. | Chapter/Heading/Sub-heading | Description
                 | CGST % | SGST/UTGST % | IGST % | Compensation Cess
  service_table  S. No. | Chapter, Section or Heading | Description
                 | CGST % | SGST/UTGST % | IGST % | Condition

Stored as two tables in law.db:
  rate_facts  one row per published schedule line (the source of record)
  rate_codes  one row per individual HSN/SAC code, pointing at its fact, so a
              lookup by a single code works even where the source groups codes

Usage: python3 harvest_gst_rates.py [--html /path/to/saved.html]
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW_DB = ROOT / "data" / "law" / "law.db"
RATES_URL = "https://cbic-gst.gov.in/hindi/gst-goods-services-rates.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_facts (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,            -- goods | service
    schedule TEXT DEFAULT '',      -- I..V for goods; '' for services
    sr_no TEXT DEFAULT '',
    hsn_sac TEXT DEFAULT '',       -- the published cell, may list several codes
    description TEXT DEFAULT '',
    cgst_rate TEXT DEFAULT '',
    sgst_rate TEXT DEFAULT '',
    igst_rate TEXT DEFAULT '',
    cess TEXT DEFAULT '',
    condition TEXT DEFAULT '',
    source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_codes (
    code TEXT NOT NULL,
    kind TEXT NOT NULL,
    fact_id INTEGER NOT NULL REFERENCES rate_facts(id),
    PRIMARY KEY (code, kind, fact_id)
);
CREATE INDEX IF NOT EXISTS idx_rate_codes_code ON rate_codes(code);
"""

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", HERE / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)


def fetch(url: str = RATES_URL) -> str:
    import urllib.request
    _thr.wait(url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=120) as r:
            blob = r.read()
        _thr.on_success(url)
        return blob.decode("utf-8", "replace")
    except Exception as e:
        _thr.on_error(url, e)
        raise


def cells_of(row_html: str) -> list[str]:
    out = []
    for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S):
        txt = re.sub(r"<[^>]+>", " ", c)
        txt = html.unescape(txt).replace("\xa0", " ")
        out.append(" ".join(txt.split()))
    return out


def parse_table(page: str, table_id: str) -> list[list[str]]:
    m = re.search(r'<table[^>]*id="' + table_id + r'"[^>]*>(.*?)</table>',
                  page, re.S | re.I)
    if not m:
        return []
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        cs = cells_of(r)
        if cs and any(cs):
            rows.append(cs)
    return rows


def norm_rate(s: str) -> str:
    """'2.5%' -> '2.5%'; '9' -> '9%' (the service table omits the sign);
    'Nil' and blank are left alone — a blank rate is not 0%."""
    s = (s or "").strip()
    if not s:
        return ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return f"{m.group(1)}%"
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return f"{s}%"
    return s


def codes_in(cell: str) -> list[str]:
    """'0202, 0203, 0204' -> ['0202','0203','0204']; 'Any chapter' -> []."""
    return [c for c in re.findall(r"\b\d{2,8}\b", cell or "")]


def main(html_path: str = "") -> None:
    page = Path(html_path).read_text(encoding="utf-8", errors="replace") \
        if html_path else fetch()

    goods = parse_table(page, "goods_table")
    services = parse_table(page, "service_table")
    print(f"goods rows: {len(goods)}   service rows: {len(services)}")

    con = sqlite3.connect(LAW_DB)
    # Both tables are derived entirely from this one page, so a clean rebuild is
    # the correct idempotent behaviour. No UNIQUE key is used: several schedule
    # lines legitimately share (schedule, sr_no, heading) and differ only in
    # description, and a uniqueness constraint on the shorter key silently
    # collapsed them (83 service facts instead of 227).
    con.executescript("DROP TABLE IF EXISTS rate_codes; DROP TABLE IF EXISTS rate_facts;")
    con.executescript(SCHEMA)

    def put(kind, schedule, sr, hsn, desc, cgst, sgst, igst, cess, cond) -> int:
        cur = con.execute(
            "INSERT INTO rate_facts"
            " (kind, schedule, sr_no, hsn_sac, description, cgst_rate, sgst_rate,"
            "  igst_rate, cess, condition, source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (kind, schedule, sr, hsn, desc, norm_rate(cgst), norm_rate(sgst),
             norm_rate(igst), cess, cond, RATES_URL))
        return cur.lastrowid

    n_facts = n_codes = 0
    # goods: skip the header row (first cell == 'Schedules')
    for cs in goods:
        if not cs or cs[0].lower().startswith("schedule"):
            continue
        cs = cs + [""] * (8 - len(cs))
        fid = put("goods", cs[0], cs[1], cs[2], cs[3], cs[4], cs[5], cs[6], cs[7], "")
        n_facts += 1
        for code in codes_in(cs[2]):
            con.execute("INSERT OR IGNORE INTO rate_codes (code,kind,fact_id) VALUES (?,?,?)",
                        (code, "goods", fid))
            n_codes += 1
    # services: skip the header and the '(1) (2) (3)' numbering row
    for cs in services:
        if not cs or cs[0].lower().startswith("s. no"):
            continue
        if cs[0].startswith("("):
            continue
        cs = cs + [""] * (7 - len(cs))
        fid = put("service", "", cs[0], cs[1], cs[2], cs[3], cs[4], cs[5], "", cs[6])
        n_facts += 1
        for code in codes_in(cs[1]):
            con.execute("INSERT OR IGNORE INTO rate_codes (code,kind,fact_id) VALUES (?,?,?)",
                        (code, "service", fid))
            n_codes += 1
    con.commit()

    print(f"rate_facts: {n_facts}   rate_codes: {n_codes}")
    print("by kind:", dict(con.execute(
        "SELECT kind, COUNT(*) FROM rate_facts GROUP BY kind").fetchall()))
    print("by schedule:", dict(con.execute(
        "SELECT schedule, COUNT(*) FROM rate_facts WHERE kind='goods'"
        " GROUP BY schedule ORDER BY schedule").fetchall()))
    print("distinct rate_codes:", con.execute(
        "SELECT COUNT(DISTINCT code) FROM rate_codes").fetchone()[0])
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="", help="parse a saved page instead of fetching")
    args = ap.parse_args()
    main(html_path=args.html)
