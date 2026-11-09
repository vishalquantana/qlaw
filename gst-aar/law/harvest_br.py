#!/usr/bin/env python3
"""Bihar GST harvester (biharcommercialtax.gov.in, official CTD).

Mechanism: Struts search form at /bweb/circular.do (strType=GSTN). Flow:
GET VWSEARCH page (session cookie via shared _https session w/ bundled
RapidSSL intermediate) → POST full form (strActionType=SEARCH + date range)
to the jsessionid action URL → results table with /bweb/download/*.pdf
(or /bweb/circularDownload.do) links. Server tarpits consecutive TLS
connections; retries + long timeouts included.

Usage: python3 harvest_br.py --max 5   (PoC slice)
       python3 harvest_br.py           (full pull, resumable)
Output: gst-aar/data/law/staging/bihar/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _https_session():
    spec = importlib.util.spec_from_file_location(
        "_https_br", Path(__file__).parent / "_https.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.session()


ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "bihar"
BASE = "https://www.biharcommercialtax.gov.in"
SEARCH = BASE + "/bweb/circular.do?strType=GSTN&strActionType=VWSEARCH"
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
PDF_RE = re.compile(r'href="([^"]*(?:\.pdf|ircularDownload)[^"]*)"', re.I)
ACTION_RE = re.compile(r'name="circular"[^>]*action="([^"]+)"')
TODAY_RE = re.compile(r'name="todayDate" value="([^"]*)"')


def clean_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        p.scheme, p.netloc,
        urllib.parse.quote(p.path, safe="/%"),
        urllib.parse.quote(p.query, safe="=&%"),
        ""))


def fetch(url: str, op, data: bytes | None = None, retries: int = 3) -> bytes:
    headers = dict(UA)
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = SEARCH
    for i in range(retries):
        _thr.wait(url)
        try:
            with op.open(urllib.request.Request(url, data=data, headers=headers),
                         timeout=120) as r:
                blob = r.read()
            _thr.on_success(url)
            return blob
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise RuntimeError("unreachable")


def search_page(html_text: str) -> tuple[str, dict]:
    """Form action URL + default POST fields parsed from the VWSEARCH page."""
    m = ACTION_RE.search(html_text)
    if not m:
        raise ValueError("no circular form action found")
    t = TODAY_RE.search(html_text)
    fields = {"todayDate": t.group(1) if t else "", "userDtls": "",
              "strType": "GSTN", "cirKeyHidden": "", "strActionType": "SEARCH",
              "fromDate": "01/01/2017", "toDate": t.group(1) if t else "",
              "wcnTaxType": "", "wlccatdesc": "", "wcnSubject": "",
              "cnNumber": "", "keyword": ""}
    return urllib.parse.urljoin(BASE + "/bweb/", html.unescape(m.group(1))), fields


def parse_results(html_text: str, base_url: str) -> list[dict]:
    """Result rows: cell text + first PDF/download link."""
    rows = []
    for tr in ROW_RE.findall(html_text)[1:]:
        m = PDF_RE.search(tr)
        if not m:
            continue
        url = clean_url(urllib.parse.urljoin(base_url, html.unescape(m.group(1))))
        if "download/CTDMailList.pdf" in url or "download/BARAuthority.pdf" in url:
            continue  # nav-shell links, not results
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        rows.append({"cells": cells, "pdf_url": url})
    return rows


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
    op = _https_session()
    try:
        shell = fetch(SEARCH, op).decode("utf-8", "replace")
        action_url, fields = search_page(shell)
        res = fetch(action_url, op,
                    urllib.parse.urlencode(fields).encode()).decode("utf-8", "replace")
    except Exception as e:
        print(f"search dead ({type(e).__name__})", file=sys.stderr)
        return
    rows = parse_results(res, action_url)
    print(f"  search returned {len(rows)} rows")
    done = 0
    with inv_path.open("a") as log:
        for row in rows:
            if row["pdf_url"] in seen:
                continue
            try:
                blob = fetch(row["pdf_url"], op)
            except Exception as e:
                print(f"  skip dead PDF {row['pdf_url']}: {type(e).__name__}", file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                continue
            name = urllib.parse.unquote(row["pdf_url"].split("?")[0].rsplit("/", 1)[-1])
            if not name.lower().endswith(".pdf"):
                name += ".pdf"
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "br_notification",
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
