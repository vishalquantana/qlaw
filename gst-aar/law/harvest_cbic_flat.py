#!/usr/bin/env python3
"""Stream B: crawl cbic-gst.gov.in flat listing pages → download notification/circular PDFs.

Follows gst-aar/download_pdfs.py throttling pattern (0.4s delay, %PDF validation).
PoC: --max 5 PDFs.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

LISTINGS = [
    ("notifications", "https://cbic-gst.gov.in/central-tax-notifications.html"),
    ("circulars", "https://cbic-gst.gov.in/circulars.html"),
    # Hindi mirror carries the same English PDFs (verified live 2026-09-06;
    # the English listings above 404). Filenames carry -Eng/-Hin markers.
    ("notifications", "https://cbic-gst.gov.in/hindi/central-tax-notifications.html"),
    ("notifications", "https://cbic-gst.gov.in/hindi/integrated-tax-notifications.html"),
    ("circulars", "https://cbic-gst.gov.in/hindi/circulars.html"),
]


def lang_hint(name: str) -> str:
    low = name.lower()
    if "hin" in low:
        return "hi"
    if "eng" in low:
        return "en"
    return ""

NAME_RE = re.compile(r"(?:(NN)-?|Notification-?No\.?\s*)?(\d+)[/-](\d{4})[-_]?([A-Za-z\(\)]*)",
                     re.I)

# Series prefix → tax category. Live cbic-gst.gov.in serves Central Tax
# notifications as NN-*.pdf (e.g. pdf/NN-26-2024_Eng.pdf, same series the
# listings title "26/2024-CT"); a prefix hit wins over a trailing language
# marker such as _Eng/_Hindi, which is not a tax category.
PREFIX_CATEGORY = {"NN": "CT"}


def fetch(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        _thr.wait(url)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
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


def parse_listing(html: str, base_url: str) -> list[dict]:
    rows = []
    for m in re.finditer(r'href="([^"]+\.pdf)"[^>]*>([^<]*)', html, re.I):
        pdf_url = urllib.parse.urljoin(base_url, m.group(1))
        if "cbic-gst.gov.in" not in pdf_url and "cbic.gov.in" not in pdf_url:
            continue
        rows.append({"title": " ".join(m.group(2).split()),
                     "pdf_url": pdf_url})
    return rows


def parse_notification_filename(name: str) -> dict:
    m = NAME_RE.search(name)
    if not m:
        return {"number": name, "category": "", "year": ""}
    num, year, cat = m.group(2), m.group(3), (m.group(4) or "").strip("_.")
    prefix = (m.group(1) or "").upper()
    if prefix in PREFIX_CATEGORY:
        cat = PREFIX_CATEGORY[prefix]
    return {"number": f"{num}/{year}", "category": cat, "year": year}


def _load_law_db():
    # Primary: Task 1 store via the test shim (works under pytest, where the
    # repo root is importable). Fallback: load the sibling law_db.py directly
    # (same pattern as harvest_cbic_api._load_law_db), because running this
    # file as a script puts gst-aar/law — not the repo root — on sys.path,
    # so `import tests.*` fails with ModuleNotFoundError.
    try:
        from tests.gst_aar_law_shim import law_db  # reuse Task 1 store via shim path
        return law_db
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "law_db", Path(__file__).parent / "law_db.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def main(max_pdfs: int = 0):
    law_db = _load_law_db()
    con = law_db.init_db()
    done = 0
    for kind, url in LISTINGS:
        try:
            html = fetch(url).decode("utf-8", "replace")
        except Exception as e:
            print(f"  listing dead, skipping {url}: {type(e).__name__}", file=sys.stderr)
            continue
        for row in parse_listing(html, url):
            dest = OUT / kind / row["pdf_url"].rsplit("/", 1)[-1]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                try:
                    blob = fetch(row["pdf_url"])
                except Exception as e:
                    print(f"  skip dead PDF {row['pdf_url']}: {type(e).__name__}", file=sys.stderr)
                    continue
                if not blob.startswith(b"%PDF"):
                    print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                    continue
                dest.write_bytes(blob)
            meta = parse_notification_filename(dest.name)
            law_db.upsert_document(con, {
                "source_url": row["pdf_url"], "kind": kind.rstrip("s"),
                "title": row["title"] or dest.name, "number": meta["number"],
                "pub_date": "", "local_path": str(dest),
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "body": ""})
            done += 1
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
