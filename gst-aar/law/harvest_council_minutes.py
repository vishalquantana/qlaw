#!/usr/bin/env python3
"""Harvest GST Council meeting minutes + discussion papers (official .gov.in).

Source page: https://www.gstcouncil.gov.in/en/gst-council-meeting
Downloads every linked PDF (minutes books 10th-55th + first discussion paper,
CEA RNR report, DoR comments, 101st Amendment copy) into
gst-aar/data/law/staging/council/ with inventory.json. Idempotent: skips
files already on disk. Validates %PDF magic.

Usage: python3 harvest_council_minutes.py [--max N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "staging" / "council"
INDEX = "https://www.gstcouncil.gov.in/en/gst-council-meeting"
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
            with urllib.request.urlopen(req, timeout=120) as r:
                blob = r.read()
                _thr.on_success(url)
                return blob
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def list_pdfs() -> list[str]:
    html = fetch(INDEX).decode("utf-8", "replace")
    return sorted({"https://www.gstcouncil.gov.in" + m
                   for m in re.findall(r'href="([^"]+\.pdf)"', html, re.I)})


def main(max_pdfs: int = 0) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    urls = list_pdfs()
    print(f"{len(urls)} PDFs listed")
    inv, done = [], 0
    for u in urls:
        dest = OUT / u.rsplit("/", 1)[-1]
        if not dest.exists():
            blob = fetch(u)
            if not blob.startswith(b"%PDF"):
                print(f"  skip non-PDF {u}", file=sys.stderr)
                continue
            dest.write_bytes(blob)
        inv.append({"source_url": u,
                    "local_path": str(dest.relative_to(ROOT.parent))})
        done += 1
        if max_pdfs and done >= max_pdfs:
            break
    (OUT / "inventory.json").write_text(json.dumps(inv, indent=1))
    print(f"done: {done} PDFs in {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
