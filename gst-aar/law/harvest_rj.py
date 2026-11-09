#!/usr/bin/env python3
"""Rajasthan GST harvester (finance.rajasthan.gov.in, official Finance Dept).

Mechanism: ASP.NET site. The CTD Struts listing (rajtax.gov.in/vatweb,
1252 records) carries no GST Tax-Type values and its SEARCH posts to a
jsessionid-bound form, so it yields only VAT amnesty rows that mention
GST in passing. The real SGST source is the Finance Dept "Tax (Goods and
Services Tax)" section: GET https://finance.rajasthan.gov.in/website/ (cookie
jar), POST back __VIEWSTATE/__EVENTVALIDATION with __EVENTTARGET for the GST
section link, follow the 302 to ShowResult.aspx — a single 587-row table
(newest first) with direct ../PDFDOCS/TAX/GST/*.pdf links + subject,
file-number and date cells. No per-row JS. Section itself is the GST filter.

Usage: python3 harvest_rj.py --max 5     (PoC slice)
       python3 harvest_rj.py             (full pull, resumable)
Output: gst-aar/data/law/staging/rajasthan/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
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
OUT = ROOT / "data" / "law" / "staging" / "rajasthan"
HOME = "https://finance.rajasthan.gov.in/website/"
RESULT = "https://finance.rajasthan.gov.in/website/ShowResult.aspx"
SECTION_TARGET = "ctl00$MainContent$dlist$ctl15$lnkSection"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PDF_RE = re.compile(r"""href=['"]([^'"]*PDFDOCS/TAX/GST/[^'"]+\.pdf)['"]""", re.I)
HIDDEN_RE = re.compile(r'name="(__VIEWSTATE|__VIEWSTATEGENERATOR|__EVENTVALIDATION)"[^>]*value="([^"]*)"')
NUM_RE = re.compile(r"\[([^\]]+)\]")
GST_RE = re.compile(r"\b[SCIG]?GST\b", re.I)


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(url: str, data: dict | None = None, op=None, retries: int = 3) -> bytes:
    opener = op or urllib.request.build_opener()
    body = urllib.parse.urlencode(data).encode() if data else None
    for i in range(retries):
        _thr.wait(url)
        try:
            req = urllib.request.Request(url, data=body, headers=UA)
            with opener.open(req, timeout=90) as r:
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


def extract_postback(html_text: str, target: str = SECTION_TARGET) -> dict:
    """ASP.NET hidden fields + GST-section EVENTTARGET for the postback."""
    fields = dict(HIDDEN_RE.findall(html_text))
    if "__VIEWSTATE" not in fields:
        raise ValueError("no VIEWSTATE on landing page")
    fields["__EVENTTARGET"] = target
    fields["__EVENTARGUMENT"] = ""
    return fields


def fetch_section(op) -> str:
    """Landing GET (seeds cookies/VIEWSTATE) + GST postback -> result HTML."""
    home = fetch(HOME, op=op).decode("utf-8", "replace")
    return fetch(HOME, extract_postback(home), op=op).decode("utf-8", "replace")


def clean_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path,
                                    parts.query, parts.fragment))


def parse_table(html_text: str, base_url: str) -> list[dict]:
    """Result rows: [sno, subject-link + [file-number], date]. PDF href
    resolved against the ShowResult page URL."""
    rows = []
    for tr in ROW_RE.findall(html_text):
        m = PDF_RE.search(tr)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [re.sub(r"\s+", " ", c) for c in cells if c.strip()]
        num = NUM_RE.search(tr)
        if num and all(num.group(1) not in c for c in cells):
            cells.append(num.group(1))
        rows.append({"cells": cells,
                     "pdf_url": clean_url(urllib.parse.urljoin(base_url, html.unescape(m.group(1))))})
    return rows


def is_gst(row: dict) -> bool:
    return bool(GST_RE.search(" ".join(row["cells"])))


def main(max_pdfs: int = 0) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inv_path = OUT / "inventory.jsonl"
    seen = set()
    if inv_path.exists():
        for line in inv_path.read_text().splitlines():
            try:
                seen.add(json.loads(line)["source_url"])
            except (KeyError, json.JSONDecodeError):
                continue
    op = _opener()
    try:
        html_text = fetch_section(op)
    except Exception as e:
        print(f"section dead: {HOME} ({type(e).__name__})", file=sys.stderr)
        return
    rows = parse_table(html_text, RESULT)
    print(f"listing: {len(rows)} GST rows (single result page)", file=sys.stderr)
    done = 0
    with inv_path.open("a") as log:
        for row in rows:
            if row["pdf_url"] in seen:
                continue
            try:
                blob = fetch(row["pdf_url"], op=op)
            except Exception as e:
                print(f"  skip dead PDF {row['pdf_url']}: {type(e).__name__}",
                      file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                continue
            name = urllib.parse.unquote(row["pdf_url"].rsplit("/", 1)[-1])
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "rj_notification",
                   "local_path": str(dest.relative_to(ROOT.parent)),
                   "cells": row["cells"][:6],
                   "sha256": hashlib.sha256(blob).hexdigest()}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            seen.add(row["pdf_url"])
            done += 1
            print(f"  {done}: {name[:70]}")
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
