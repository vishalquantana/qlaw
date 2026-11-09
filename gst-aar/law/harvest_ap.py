#!/usr/bin/env python3
"""Andhra Pradesh GST harvester (goir.ap.gov.in, official G.O. repository).

AP has no separate Commercial Taxes department in the G.O. repository: CTD
notifications issue under REVENUE, so the search runs with DDLDeptname=REV.

Mechanism (verified 2026-09-12):
  ASP.NET WebForms search. POST the homepage with a dd-mm-yyyy date window.
  The result grid caps at 100 rows per response and its pager is an
  UpdatePanel postback that does NOT replay under plain urllib (clicking
  Repeater1/rptPager lnkPage returns page 1 again), so instead of paging we
  run one narrow window per calendar year -- each stays under the cap.
  Row link: javascript:downloadFile("<gid>","E")
            -> dgo.ashx?gid=<gid>&fileType=E
  The PDF is served only to a session that has run the search; a bare GET of
  dgo.ashx returns 0 bytes, so the download must reuse the search session.

Usage: python3 harvest_ap.py --max 3     (PoC slice)
       python3 harvest_ap.py             (full pull, resumable)
Output: gst-aar/data/law/staging/andhra-pradesh/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "andhra-pradesh"
INDEX = "https://goir.ap.gov.in/"
BASE = "https://goir.ap.gov.in/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

FIRST_YEAR = 2017

# Substantive tax-law terms. Deliberately excludes bare "VAT" (too noisy) and
# bare "Commercial Taxes" (matches thousands of CTD service matters).
GST_TERMS = ("GST", "CGST", "SGST", "IGST", "goods and services tax",
             "value added tax", "APGST")
SEARCH_TERMS = ("GST", "Goods and Services Tax")

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
DL_RE = re.compile(r'downloadFile\(\s*"(\d+)"\s*,\s*"(\w)"\s*\)')
VIEWSTATE_RE = re.compile(r'name="__VIEWSTATE"[^>]*value="([^"]*)"')
VSGEN_RE = re.compile(r'name="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"')


def _session() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(op, url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        _thr.wait(url)
        try:
            with op.open(urllib.request.Request(url, headers=UA), timeout=60) as r:
                blob = r.read()
            _thr.on_success(url)
            return blob
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def _post(op, data: dict, retries: int = 3) -> str:
    body = urllib.parse.urlencode(data).encode()
    hdrs = {**UA, "Content-Type": "application/x-www-form-urlencoded"}
    for i in range(retries):
        _thr.wait(INDEX)
        try:
            with op.open(urllib.request.Request(INDEX, data=body, headers=hdrs),
                         timeout=90) as r:
                text = r.read().decode("utf-8", "replace")
            _thr.on_success(INDEX)
            return text
        except Exception as e:
            _thr.on_error(INDEX, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} post: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def _hidden(page: str, pattern: re.Pattern) -> str:
    m = pattern.search(page)
    return m.group(1) if m else ""


def search(op, term: str, frm: str, to: str) -> str:
    """Fresh homepage (new VIEWSTATE) then one search POST."""
    home = _get(op, INDEX).decode("utf-8", "replace")
    data = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": _hidden(home, VIEWSTATE_RE),
        "__VIEWSTATEGENERATOR": _hidden(home, VSGEN_RE),
        "ctl00$ContentPlaceHolder1$DDLDeptname": "REV",
        "ctl00$ContentPlaceHolder1$sectddl": "-1",
        "ctl00$ContentPlaceHolder1$DDLGoType": "-1",
        "ctl00$ContentPlaceHolder1$DdlGo_cat": "-1",
        "ctl00$ContentPlaceHolder1$txtGoNo": "",
        "ctl00$ContentPlaceHolder1$txtfrmdate": frm,
        "ctl00$ContentPlaceHolder1$txttodate": to,
        "ctl00$ContentPlaceHolder1$fAmount": "",
        "ctl00$ContentPlaceHolder1$tAmount": "",
        "ctl00$ContentPlaceHolder1$txtSearchText": term,
        "ctl00$ContentPlaceHolder1$BtnSearch": "Search",
    }
    return _post(op, data)


def parse_rows(page: str) -> list[dict]:
    """One dict per result row that carries a download link."""
    rows = []
    for tr in ROW_RE.findall(page):
        m = DL_RE.search(tr)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        rows.append({"gid": m.group(1), "file_type": m.group(2), "cells": cells})
    return rows


def abstract_of(row: dict) -> str:
    """The abstract is the long text cell; fall back to the joined row."""
    for c in row["cells"]:
        if len(c) > 40:
            return c
    return " ".join(row["cells"])


def is_gst(row: dict) -> bool:
    text = abstract_of(row).lower()
    return any(t.lower() in text for t in GST_TERMS)


def gid_of(row: dict) -> str:
    return row["gid"]


def main(max_pdfs: int = 0) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inv_path = OUT / "inventory.jsonl"
    seen = set()
    if inv_path.exists():
        for line in inv_path.read_text().splitlines():
            try:
                seen.add(json.loads(line)["gid"])
            except (KeyError, json.JSONDecodeError):
                continue
    op = _session()
    today = datetime.date.today()
    this_year = today.year

    # 1. enumerate candidates year by year (each window stays under the 100 cap)
    candidates: dict[str, dict] = {}
    for year in range(FIRST_YEAR, this_year + 1):
        frm = f"01-01-{year}"
        to = today.strftime("%d-%m-%Y") if year == this_year else f"31-12-{year}"
        for term in SEARCH_TERMS:
            try:
                page = search(op, term, frm, to)
            except Exception as e:
                print(f"  skip {year} {term!r}: {type(e).__name__}", file=sys.stderr)
                continue
            rows = parse_rows(page)
            kept = [r for r in rows if is_gst(r)]
            print(f"  {year} {term!r}: {len(rows)} rows, {len(kept)} GST",
                  file=sys.stderr)
            for r in kept:
                candidates.setdefault(r["gid"], r)

    print(f"candidates: {len(candidates)} GST G.O.s "
          f"({len(seen)} already held)", file=sys.stderr)

    # 2. download within the same session (dgo.ashx needs the search session)
    done = 0
    with inv_path.open("a") as log:
        for gid, row in candidates.items():
            if gid in seen:
                continue
            url = f"{BASE}dgo.ashx?gid={gid}&fileType={row['file_type']}"
            try:
                blob = _get(op, url)
            except Exception as e:
                print(f"  skip dead {url}: {type(e).__name__}", file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {url} ({len(blob)} bytes)", file=sys.stderr)
                continue
            cells = row["cells"]
            gon = cells[1] if len(cells) > 1 else ""
            date = cells[2] if len(cells) > 2 else ""
            name = re.sub(r"[^\w.-]+", "_", f"AP_{gon}_{date}.pdf").strip("_")
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": url, "kind": "ap_notification", "gid": gid,
                   "local_path": str(dest.relative_to(ROOT.parent)),
                   "cells": cells[:6], "go_no": gon, "go_date": date,
                   "sha256": hashlib.sha256(blob).hexdigest()}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            seen.add(gid)
            done += 1
            print(f"  {done}: {name[:70]}", flush=True)
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
