#!/usr/bin/env python3
"""Telangana GST harvester (tgct.gov.in, official Commercial Taxes Dept).

Mechanism: ASP.NET GridView index pages list every document (number, date,
subject); each row downloads via __doPostBack simulation (VIEWSTATE-chained
session). TLS: server omits the intermediate — bundle certs/digicert-g2-
intermediate.pem with certifi (see _context()).

Pages (row counts measured 2026-09-06):
  Tax notifications   bind_GST_NotificationsTax.aspx?type=Tax        (~434 rows)
  Rate notifications  bind_GST_NotificationsRate.aspx?type=Rate       (~199 rows)
  Circulars           bind_GST_Circulars.aspx?type=Circulars            (~27 rows)
Each row carries TWO links: state G.O. (lblCSTNoteNo) and CBIC doc
(lblCibicNoteNo). Both are harvested; kinds tg_notification / tg_cbic_doc.

Usage: python3 harvest_tgct.py --max 3        (PoC slice)
       python3 harvest_tgct.py                (full pull, resumable)
Output: gst-aar/data/law/staging/telangana/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "telangana"
CERTS = Path(__file__).parent / "certs" / "digicert-g2-intermediate.pem"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

PAGES = {
    "tg_notification": "https://tgct.gov.in/tgportal/GST/Uploads/bind_GST_NotificationsTax.aspx?type=Tax",
    "tg_rate": "https://tgct.gov.in/tgportal/GST/Uploads/bind_GST_NotificationsRate.aspx?type=Rate",
    "tg_circular": "https://tgct.gov.in/tgportal/GST/Uploads/bind_GST_Circulars.aspx?type=Circulars",
}

GRID_RE = re.compile(r'<table[^>]*gvGSTFilesBind[^>]*>(.*?)</table>', re.S)
ROW_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
CELL_RE = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.S)
TARGET_RE = re.compile(r"__doPostBack\(&#39;(ctl00\$ContentPlaceHolder1\$gvGSTFilesBind\$ctl\d+\$lbl\w+)&#39;")


def _context() -> ssl.SSLContext:
    try:
        import certifi
        bundle = certifi.where()
    except ImportError:
        bundle = None
    ctx = ssl.create_default_context(cafile=bundle) if bundle else ssl.create_default_context()
    if CERTS.exists():
        ctx.load_verify_locations(cafile=str(CERTS))
    return ctx


def _session():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_context()),
        urllib.request.HTTPCookieProcessor(cj))


def fetch(url: str, op, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            with op.open(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def parse_grid(html_text: str) -> list[dict]:
    """Rows from the GridView table: cells + per-row postback targets."""
    m = GRID_RE.search(html_text)
    if not m:
        return []
    rows = []
    for i, tr in enumerate(ROW_RE.findall(m.group(1))[1:]):  # skip header
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace("\xa0", " ")
                 for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        targets = [t for t in TARGET_RE.findall(tr)]
        if cells:
            rows.append({"idx": i, "cells": cells, "targets": targets})
    return rows


def row_key(page_url: str, idx: int, target: str) -> str:
    """Stable dedup key: page + row position + control leaf (leaves like
    lblCSTNoteNo repeat across rows, so the leaf alone collides)."""
    return f"{page_url}#r{idx}-{target.split('$')[-1]}"


def hidden_fields(html_text: str) -> dict:
    out = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'name="' + name + r'"[^>]*value="([^"]*)"', html_text)
        out[name] = m.group(1) if m else ""
    return out


def postback(op, url: str, fields: dict, target: str) -> tuple[bytes, dict]:
    """Simulate one GridView download click. Returns (body, fresh fields)."""
    data = {**fields, "__EVENTTARGET": target, "__EVENTARGUMENT": ""}
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(data).encode(),
        headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
    with op.open(req, timeout=120) as r:
        body = r.read()
    try:
        text = body.decode("utf-8", "replace")
        fresh = hidden_fields(text)
        if fresh["__VIEWSTATE"]:
            fields.update(fresh)
    except Exception:
        pass
    return body, fields


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
        for kind, url in PAGES.items():
            op = _session()
            html_text = fetch(url, op).decode("utf-8", "replace")
            fields = hidden_fields(html_text)
            for row in parse_grid(html_text):
                for target in row["targets"]:
                    doc_url = row_key(url, row["idx"], target)
                    if doc_url in seen:
                        continue
                    body, fields = postback(op, url, fields, target)
                    if not body.startswith(b"%PDF"):
                        print(f"  skip non-PDF {target}", file=sys.stderr)
                        continue
                    digest = hashlib.sha256(body).hexdigest()[:16]
                    dest = OUT / f"{kind}-{digest}.pdf"
                    dest.write_bytes(body)
                    rec = {"source_url": doc_url, "kind": kind,
                           "local_path": str(dest.relative_to(ROOT.parent)),
                           "cells": row["cells"][:6], "sha256": digest}
                    log.write(json.dumps(rec) + "\n")
                    log.flush()
                    seen.add(doc_url)
                    done += 1
                    print(f"  {done}: {kind} {row['cells'][0][:60] if row['cells'] else ''}")
                    time.sleep(0.4)
                    if max_pdfs and done >= max_pdfs:
                        print(f"PoC slice done: {done} PDFs")
                        return
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
