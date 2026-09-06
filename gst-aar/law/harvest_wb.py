#!/usr/bin/env python3
"""West Bengal GST harvester (comtax.wb.gov.in, official CTD).

Mechanism: single static HTML table (2017→2026, ~460 rows) with direct
relative PDF links (bare filenames + ../GST_Acts_Rules/). Plain GET, no JS,
no login. Covers state notifications + WBGST Act/Rules/ordinances as bonus.

Usage: python3 harvest_wb.py --max 3     (PoC slice)
       python3 harvest_wb.py             (full pull, resumable)
Output: gst-aar/data/law/staging/west-bengal/*.pdf + inventory.jsonl
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
    """Shared TLS helper (legacy-reneg + bundled intermediates), loaded like
    the test shim does so this module stays importable from anywhere."""
    spec = importlib.util.spec_from_file_location(
        "_https_wb", Path(__file__).parent / "_https.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.session()

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "west-bengal"
INDEX = "https://comtax.wb.gov.in/GST/GST_Notifications/gst_notifications_state.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PDF_RE = re.compile(r'href="([^"]+\.pdf)"', re.I)


def fetch(url: str, op=None, retries: int = 3) -> bytes:
    opener = op or urllib.request.build_opener()
    for i in range(retries):
        try:
            with opener.open(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def parse_table(html_text: str, base_url: str) -> list[dict]:
    """Table rows: cell text + first PDF link resolved against the page URL."""
    rows = []
    for tr in ROW_RE.findall(html_text)[1:]:  # skip header
        m = PDF_RE.search(tr)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        rows.append({"cells": cells,
                     "pdf_url": urllib.parse.urljoin(base_url, m.group(1))})
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
    try:
        op = _https_session()
        html_text = fetch(INDEX, op).decode("utf-8", "replace")
    except Exception as e:
        print(f"index dead: {INDEX} ({type(e).__name__})", file=sys.stderr)
        return
    done = 0
    with inv_path.open("a") as log:
        for row in parse_table(html_text, INDEX):
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
            name = urllib.parse.unquote(row["pdf_url"].rsplit("/", 1)[-1])
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "wb_notification",
                   "local_path": str(dest.relative_to(ROOT.parent)),
                   "cells": row["cells"][:6],
                   "sha256": hashlib.sha256(blob).hexdigest()}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            seen.add(row["pdf_url"])
            done += 1
            print(f"  {done}: {name[:70]}")
            time.sleep(0.4)
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
