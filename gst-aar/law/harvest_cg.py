#!/usr/bin/env python3
"""Chhattisgarh GST harvester (comtax.cg.nic.in, official Commercial Tax).

Mechanism: NO central SGST-notification listing. notification.htm hub covers
only VAT-era year pages (2002–2013, zero GST mentions). Fallback PoC: sweep
the Circ1.htm year hub (2023.htm, 2024.htm, …) + GSTAT.htm for direct
pages/Important/*.pdf links with GST in the name (e.g. GST Refund-98_2024).
Plain GET, no JS. Thin yield — see METHOD note. Proper coverage likely
needs the CG e-Gazette.

Usage: python3 harvest_cg.py --max 5   (PoC slice)
Output: gst-aar/data/law/staging/chhattisgarh/*.pdf + inventory.jsonl
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
        "_https_cg", Path(__file__).parent / "_https.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.session()

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "chhattisgarh"
BASE = "https://comtax.cg.nic.in/"
HUBS = [BASE + "Circ1.htm", BASE + "GSTAT.htm"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

HREF_RE = re.compile(r'href="([^"]+)"', re.I)


def clean_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        p.scheme, p.netloc,
        urllib.parse.quote(p.path, safe="/%"),
        urllib.parse.quote(p.query, safe="=&%"),
        ""))


def fetch(url: str, op=None, retries: int = 3) -> bytes:
    opener = op or urllib.request.build_opener()
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with opener.open(req, timeout=90) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def parse_hub(html_text: str, base_url: str) -> tuple[list[dict], list[str]]:
    """GST-named PDFs on this page + year-hub sub-pages to follow."""
    rows, subs = [], []
    for href in set(HREF_RE.findall(html_text)):
        href = html.unescape(href)
        if href.lower().endswith(".pdf") and "gst" in href.lower():
            rows.append({"cells": [urllib.parse.unquote(href.rsplit("/", 1)[-1])],
                         "pdf_url": clean_url(urllib.parse.urljoin(base_url, href))})
        elif re.search(r"20\d\d\.htm$", href):
            subs.append(urllib.parse.urljoin(base_url, href))
    return rows, sorted(set(subs))


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
    rows: list[dict] = []
    queue = list(HUBS)
    visited = set()
    op = _https_session()
    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            page = fetch(url, op).decode("utf-8", "replace")
        except Exception as e:
            print(f"  page dead {url}: {type(e).__name__}", file=sys.stderr)
            continue
        found, subs = parse_hub(page, url)
        rows.extend(found)
        queue.extend(s for s in subs if s not in visited)
        time.sleep(0.4)
    uniq, seen_urls = [], set()
    for r in rows:
        if r["pdf_url"] not in seen_urls:
            uniq.append(r)
            seen_urls.add(r["pdf_url"])
    print(f"  hub sweep found {len(uniq)} GST PDFs")
    done = 0
    with inv_path.open("a") as log:
        for row in uniq:
            if row["pdf_url"] in seen:
                continue
            try:
                blob = fetch(row["pdf_url"], op)
            except Exception as e:
                print(f"  skip dead PDF: {type(e).__name__}", file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                continue
            name = urllib.parse.unquote(row["pdf_url"].split("?")[0].rsplit("/", 1)[-1])
            dest = OUT / name
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "cg_notification",
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
