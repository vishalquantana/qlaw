#!/usr/bin/env python3
"""Punjab GST harvester (taxation.punjab.gov.in, official Excise & Taxation).

Mechanism: NO dedicated static SGST-notification listing exists; portal is a
JS-menu CMS (Act&Rules > GST > Notifications needs rendering). Fallback PoC:
sweep the homepage + /products/content listing pages for direct
/attachments/*GST*.pdf links (monthly GST Updates, calendars, taxpayer
notices). Direct hrefs, plain GET. Yield is GST collateral, NOT numbered
SGST notifications — see METHOD note. Proper coverage needs JS render or
the Punjab e-Gazette.

Usage: python3 harvest_pb.py --max 5   (PoC slice)
Output: gst-aar/data/law/staging/punjab/*.pdf + inventory.jsonl
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
OUT = ROOT / "data" / "law" / "staging" / "punjab"
BASE = "https://taxation.punjab.gov.in"
INDEX = BASE + "/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

HREF_RE = re.compile(r'href="([^"]+)"', re.I)
CONTENT_RE = re.compile(r'href="(/products/content/\d+)"')


def clean_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        p.scheme, p.netloc,
        urllib.parse.quote(p.path, safe="/%"),
        urllib.parse.quote(p.query, safe="=&%"),
        ""))


def fetch(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        _thr.wait(url)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
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


def parse_attachments(html_text: str, base_url: str) -> list[dict]:
    """GST-titled /attachments PDFs + content-page URLs worth sweeping."""
    rows = []
    for href in set(HREF_RE.findall(html_text)):
        if "/attachments/" not in href:
            continue
        if "gst" not in href.lower():
            continue
        rows.append({"cells": [urllib.parse.unquote(href.rsplit("/", 1)[-1])],
                     "pdf_url": clean_url(urllib.parse.urljoin(base_url, html.unescape(href)))})
    pages = sorted(set(CONTENT_RE.findall(html_text)))
    return rows, pages


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
        home = fetch(INDEX).decode("utf-8", "replace")
    except Exception as e:
        print(f"index dead: {INDEX} ({type(e).__name__})", file=sys.stderr)
        return
    rows, pages = parse_attachments(home, INDEX)
    for p in pages[:10]:  # bounded sweep of listing sub-pages
        try:
            sub = fetch(urllib.parse.urljoin(BASE, p)).decode("utf-8", "replace")
        except Exception as e:
            print(f"  page dead {p}: {type(e).__name__}", file=sys.stderr)
            continue
        rows.extend(parse_attachments(sub, BASE + p)[0])
    # dedupe, keep order
    uniq, seen_urls = [], set()
    for r in rows:
        if r["pdf_url"] not in seen_urls:
            uniq.append(r)
            seen_urls.add(r["pdf_url"])
    done = 0
    with inv_path.open("a") as log:
        for row in uniq:
            if row["pdf_url"] in seen:
                continue
            if not row["pdf_url"].lower().endswith(".pdf"):
                continue
            try:
                blob = fetch(row["pdf_url"])
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
            rec = {"source_url": row["pdf_url"], "kind": "pb_notification",
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
