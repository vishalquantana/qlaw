#!/usr/bin/env python3
"""Gujarat GST harvester (commercialtax.gujarat.gov.in, official CTD).

Mechanism: TCS Struts app (same family as Bihar/Rajasthan). POST-backed
paginated table (939 records / ~31 pages x 30 rows) with per-row hidden
<input name="urlOpenList1" value="download/cir_noti/NOTI/*.pdf"> resolved
against /vatwebsite/ via window.open. Tax Type column filters GST (+CESS,
which here is GST compensation-cess business, e.g. GSTAT appeals).
Plain GET page 1; pages 2+ via POST currentPage/PageSize (cookie jar kept).
No login. Filenames contain spaces/commas -> URL-quoted before fetch.

Usage: python3 harvest_gj.py --max 5     (PoC slice)
       python3 harvest_gj.py             (full pull, resumable)
Output: gst-aar/data/law/staging/gujarat/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import html
import http.cookiejar
import importlib.util
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "gujarat"
INDEX = ("https://commercialtax.gujarat.gov.in/vatwebsite/circular.do"
         "?strType=NOTI&strActionType=LIST")
BASE = "https://commercialtax.gujarat.gov.in/vatwebsite/"
PAGE_SIZE = 30
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
HIDDEN_RE = re.compile(r'name="urlOpenList\d?"\s+value="([^"]+)"')
TOTAL_RE = re.compile(r"Total Records\s*:\s*(\d+)")

GST_TAX_TYPES = {"GST", "CESS"}


def _https_session():
    """Shared TLS helper (Entrust intermediate lives in certs/), loaded like
    the WB harvester so this module stays importable from anywhere."""
    spec = importlib.util.spec_from_file_location(
        "_https_gj", Path(__file__).parent / "_https.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ctx = mod.context()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _opener() -> urllib.request.OpenerDirector:
    return _https_session()


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


def clean_url(url: str) -> str:
    """Quote spaces/commas in listing-derived paths (page-1 notes: most
    hrefs need quoting)."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path,
                                    parts.query, parts.fragment))


def parse_table(html_text: str, base_url: str) -> list[dict]:
    """Struts rows: hidden urlOpenList input + cells [sno, tax type,
    category, number+subject, date]. PDF path resolved against base_url."""
    rows = []
    for tr in ROW_RE.findall(html_text):
        m = HIDDEN_RE.search(tr)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        pdf_url = clean_url(urllib.parse.urljoin(base_url, m.group(1).strip()))
        rows.append({"cells": cells, "pdf_url": pdf_url,
                     "tax_type": cells[1].strip().upper() if len(cells) > 1 else ""})
    return rows


def is_gst(row: dict) -> bool:
    return row["tax_type"] in GST_TAX_TYPES


def total_records(html_text: str) -> int:
    m = TOTAL_RE.search(html_text)
    return int(m.group(1)) if m else 0


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
        page1 = fetch(INDEX, op=op).decode("utf-8", "replace")
    except Exception as e:
        print(f"index dead: {INDEX} ({type(e).__name__})", file=sys.stderr)
        return
    total = total_records(page1)
    pages = max(1, -(-total // PAGE_SIZE)) if total else 1
    print(f"listing: {total} records / {pages} pages", file=sys.stderr)
    done = 0
    with inv_path.open("a") as log:
        for page in range(1, pages + 1):
            if page == 1:
                html_text = page1
            else:
                try:
                    html_text = fetch(
                        INDEX, {"currentPage": str(page), "PageSize": str(PAGE_SIZE)},
                        op=op).decode("utf-8", "replace")
                except Exception as e:
                    print(f"  skip dead page {page}: {type(e).__name__}", file=sys.stderr)
                    continue
            rows = parse_table(html_text, BASE)
            if not rows:
                break
            for row in rows:
                if not is_gst(row) or row["pdf_url"] in seen:
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
                rec = {"source_url": row["pdf_url"], "kind": "gj_notification",
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
