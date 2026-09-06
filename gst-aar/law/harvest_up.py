#!/usr/bin/env python3
"""Uttar Pradesh GST harvester (comtax.up.nic.in, official CTD).

Mechanism: hub page (GSThome/en/gst-notification.html) links year subpages
notification/<YYYY-YY>/notice1.html (10 years: 2017-18..2026-27). Each year
page is a static table with direct relative PDF hrefs
(../<year>/{English,Hindi}/*.pdf, English+Hindi twins per serial). Plain GET,
no JS, no login.

Usage: python3 harvest_up.py --max 5    (PoC slice, newest year first)
       python3 harvest_up.py            (full pull, resumable)
Output: gst-aar/data/law/staging/uttar-pradesh/*.pdf + inventory.jsonl
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
OUT = ROOT / "data" / "law" / "staging" / "uttar-pradesh"
HUB = "https://comtax.up.nic.in/GSThome/en/gst-notification.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

YEAR_RE = re.compile(r'href="((?:[^"]*?/)?notification/\d{4}-\d{2}/notice1\.html)"', re.I)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PDF_RE = re.compile(r'href="([^"]+\.pdf)"', re.I)


def clean(url: str) -> str:
    """Percent-encode raw spaces etc. in year-page hrefs (some contain spaces)."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(
        path=urllib.parse.quote(parts.path, safe="/%"),
        query=urllib.parse.quote(parts.query, safe="&=%")))


def fetch(url: str, retries: int = 3) -> bytes:
    url = clean(url)
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


def _cells(tr: str) -> list[str]:
    cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
             for c in CELL_RE.findall(tr)]
    return [c for c in cells if c]


def parse_hub(html_text: str, base_url: str) -> list[str]:
    """Year-page URLs, newest first."""
    urls = sorted({urllib.parse.urljoin(base_url, m) for m in YEAR_RE.findall(html_text)},
                  reverse=True)
    return urls


def parse_year(html_text: str, base_url: str) -> list[dict]:
    """Year-table rows: every PDF link with its row cells (English+Hindi twins)."""
    rows = []
    for tr in ROW_RE.findall(html_text)[1:]:  # skip header
        cells = _cells(tr)
        for m in PDF_RE.finditer(tr):
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
        years = parse_hub(fetch(HUB).decode("utf-8", "replace"), HUB)
    except Exception as e:
        print(f"hub dead: {HUB} ({type(e).__name__})", file=sys.stderr)
        return
    done = 0
    with inv_path.open("a") as log:
        for year_url in years:
            try:
                page = fetch(year_url).decode("utf-8", "replace")
            except Exception as e:
                print(f"  year page dead {year_url}: {type(e).__name__}", file=sys.stderr)
                continue
            for row in parse_year(page, year_url):
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
                name = urllib.parse.unquote(row["pdf_url"].rsplit("/", 1)[-1])
                dest = OUT / name
                if dest.exists():
                    dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
                dest.write_bytes(blob)
                rec = {"source_url": row["pdf_url"], "kind": "up_notification",
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
