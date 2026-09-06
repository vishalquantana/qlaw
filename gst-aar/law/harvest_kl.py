#!/usr/bin/env python3
"""Kerala GST harvester (keralataxes.gov.in, official State GST Dept).

Mechanism: two static WordPress pages, one notification table each, no
pagination, no JS (plain GET; http host canonical, curl follows to host):
  - /2017/10/25/kgst-notifications/  (KGST table, ~19 rows)
  - /2019/02/08/state-tax-notifications/ (State Tax table, ~1 row, may overlap)
Direct /wp-content/uploads/*.pdf links. Table scoped to entry-content so nav /
sidebar boilerplate PDFs are ignored. Rows deduped by PDF URL.

Usage: python3 harvest_kl.py --max 5    (PoC slice)
       python3 harvest_kl.py            (full pull, resumable)
Output: gst-aar/data/law/staging/kerala/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "kerala"
BASE = "http://www.keralataxes.gov.in"
INDEX_URLS = [BASE + "/2017/10/25/kgst-notifications/",
              BASE + "/2019/02/08/state-tax-notifications/"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

ENTRY_RE = re.compile(r'class="entry-content"[^>]*>', re.S)
TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PDF_RE = re.compile(r'href="([^"]*?/wp-content/uploads/[^"]+\.pdf[^"]*)"', re.I)


def fetch(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def parse_table(html_text: str, base_url: str) -> list[dict]:
    """Entry-content table rows: cell text + first uploads PDF link per row."""
    m = ENTRY_RE.search(html_text)
    scope = html_text[m.end():] if m else html_text
    tables = TABLE_RE.findall(scope)
    table_html = max(tables, key=len) if tables else scope
    rows = []
    for tr in ROW_RE.findall(table_html)[1:]:  # skip header
        pm = PDF_RE.search(tr)
        if not pm:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        pdf_url = urllib.parse.urljoin(base_url, html.unescape(pm.group(1)))
        rows.append({"cells": cells, "pdf_url": pdf_url})
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
    done = 0
    with inv_path.open("a") as log:
        for index_url in INDEX_URLS:
            try:
                html_text = fetch(index_url).decode("utf-8", "replace")
            except Exception as e:
                print(f"index dead: {index_url} ({type(e).__name__})", file=sys.stderr)
                continue
            for row in parse_table(html_text, index_url):
                if row["pdf_url"] in seen:
                    continue
                try:
                    blob = fetch(row["pdf_url"])
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
                rec = {"source_url": row["pdf_url"], "kind": "kl_notification",
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
            time.sleep(0.4)
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
