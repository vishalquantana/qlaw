#!/usr/bin/env python3
"""Assam GST harvester (tax.assam.gov.in, official Commissionerate).

Mechanism: single static HTML table (GST_Notifications_COT.html, ~77 PDFs),
rows are <tr bgcolor="#ffffff"> with 3 cells (Sl.No / Notification No+date /
title link to ../GST/FORMATS/*.pdf). Plain GET, no JS. Sister page
GST_Notifications.html (Finance dept) shares the FORMATS dir.

Usage: python3 harvest_as.py --max 5   (PoC slice)
       python3 harvest_as.py           (full pull, resumable)
Output: gst-aar/data/law/staging/assam/*.pdf + inventory.jsonl
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
OUT = ROOT / "data" / "law" / "staging" / "assam"
INDEX = "https://tax.assam.gov.in/AssamTimsInfo/content/GST_Notifications_COT.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

ROW_RE = re.compile(r'<tr[^>]*bgcolor="#ffffff"[^>]*>(.*?)</tr>', re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PDF_RE = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def clean_url(url: str) -> str:
    """Percent-encode spaces/parens in path+query (e.g. '12-2019 (Tax).pdf')."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        p.scheme, p.netloc,
        urllib.parse.quote(p.path, safe="/%"),
        urllib.parse.quote(p.query, safe="=&%"),
        ""))


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
    """White data rows: cell text + first PDF link resolved against page URL."""
    rows = []
    for tr in ROW_RE.findall(html_text):
        m = PDF_RE.search(tr)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        rows.append({"cells": cells,
                     "pdf_url": clean_url(urllib.parse.urljoin(base_url, html.unescape(m.group(1))))})
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
        html_text = fetch(INDEX).decode("utf-8", "replace")
    except Exception as e:
        print(f"index dead: {INDEX} ({type(e).__name__})", file=sys.stderr)
        return
    done = 0
    with inv_path.open("a") as log:
        for row in parse_table(html_text, INDEX):
            if row["pdf_url"] in seen:
                continue
            try:
                blob = fetch(row["pdf_url"])
            except Exception as e:
                print(f"  skip dead PDF {row['pdf_url']}: {type(e).__name__}", file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                continue
            name = urllib.parse.unquote(row["pdf_url"].split("?")[0].rsplit("/", 1)[-1])
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "as_notification",
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
