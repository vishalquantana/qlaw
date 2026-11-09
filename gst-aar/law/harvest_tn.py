#!/usr/bin/env python3
"""Tamil Nadu GST harvester (tnvat.tn.gov.in, official CTD).

Mechanism: the notifications page (notification_by_ctt.jsp) renders an empty
<table id="example"> filled at runtime via fetchfile.js: GET
/ctdportal/FileOptionServlet?option=19&subtype=Notifications+and+Circulars+by+CCT
returns JSON {"files": [{name, description, date, adminFileId, ...}]} (71 rows,
newest first). Each file downloads via /ctdportal/DownloadServlet?fileId=<id>.
Plain GET, no browser needed — curl reaches both endpoints. NOTE: the older
tngst_rules_notification.jsp page embeds direct ../documents/... PDF links but
those 2017-18 files are 404 (link rot); the servlet path is the live one.

Usage: python3 harvest_tn.py --max 5    (PoC slice)
       python3 harvest_tn.py            (full pull, resumable)
Output: gst-aar/data/law/staging/tamil-nadu/*.pdf + inventory.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "tamil-nadu"
BASE = "https://tnvat.tn.gov.in"
SERVLET = (BASE + "/ctdportal/FileOptionServlet?option=19&subtype="
           + urllib.parse.quote("Notifications and Circulars by CCT", safe=""))
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)


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


def download_url(admin_file_id: str) -> str:
    return (BASE + "/ctdportal/DownloadServlet?fileId="
            + urllib.parse.quote(admin_file_id, safe=""))


def parse_files(payload: dict) -> list[dict]:
    """Servlet JSON -> rows (cells + DownloadServlet URL). Pure function."""
    rows = []
    files = payload.get("files", []) if isinstance(payload, dict) else []
    for f in files:
        fid = (f.get("adminFileId") or "").strip()
        if not fid:
            continue
        cells = [str(f.get("name", "")).strip(),
                 str(f.get("date", "")).strip(),
                 str(f.get("description", "")).strip()]
        cells = [c for c in cells if c]
        rows.append({"cells": cells, "pdf_url": download_url(fid),
                     "file_id": fid, "name": f.get("name", "")})
    return rows


def safe_name(name: str, file_id: str) -> str:
    slug = re.sub(r"[^\w\-. ]+", "_", (name or "").strip())[:80].strip() or "tn-doc"
    if not slug.lower().endswith(".pdf"):
        slug += ".pdf"
    return slug


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
        payload = json.loads(fetch(SERVLET).decode("utf-8", "replace"))
    except Exception as e:
        print(f"servlet dead: {SERVLET} ({type(e).__name__})", file=sys.stderr)
        return
    done = 0
    with inv_path.open("a") as log:
        for row in parse_files(payload):
            if row["pdf_url"] in seen:
                continue
            try:
                blob = fetch(row["pdf_url"])
            except Exception as e:
                print(f"  skip dead PDF {row['pdf_url'][:80]}: {type(e).__name__}",
                      file=sys.stderr)
                continue
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {row['pdf_url'][:80]}", file=sys.stderr)
                continue
            dest = OUT / safe_name(row["name"], row["file_id"])
            if dest.exists():
                dest = OUT / (hashlib.sha256(blob).hexdigest()[:12] + "-" + dest.name)
            dest.write_bytes(blob)
            rec = {"source_url": row["pdf_url"], "kind": "tn_notification",
                   "local_path": str(dest.relative_to(ROOT.parent)),
                   "cells": row["cells"][:6],
                   "sha256": hashlib.sha256(blob).hexdigest()}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            seen.add(row["pdf_url"])
            done += 1
            print(f"  {done}: {dest.name[:70]}")
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
