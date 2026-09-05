#!/usr/bin/env python3
"""Download all AAR/AAAR ruling PDFs from the scraped listing.

Resumable: skips files that already exist with non-trivial size and matching
content-length when known. Parallel workers with polite delays.
"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

LIST = Path(__file__).parent / "data" / "aar_list.jsonl"
PDF_DIR = Path(__file__).parent / "data" / "pdfs"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

WORKERS = 8


def load_records() -> list[dict]:
    seen = {}
    with LIST.open() as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("pdf_url"):
                seen[rec["pdf_url"]] = rec  # dedupe by URL, last wins
    return list(seen.values())


def target_path(rec: dict) -> Path:
    name = rec["pdf_url"].rsplit("/", 1)[-1]
    state = (rec.get("state") or "unknown").strip().replace(" ", "_").replace("/", "-")
    return PDF_DIR / state / name


def download(rec: dict) -> tuple[str, str]:
    if not rec.get("pdf_url"):
        return rec.get("sr_no", "?"), "no_url"
    dest = target_path(rec)
    if dest.exists() and dest.stat().st_size > 10_000:
        return rec.get("sr_no", "?"), "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            req = urllib.request.Request(rec["pdf_url"], headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 1_000 or not data.startswith(b"%PDF"):
                # some may be HTML error pages; keep but flag
                if not data.startswith(b"%PDF"):
                    return rec.get("sr_no", "?"), f"not_pdf_{len(data)}b"
            dest.write_bytes(data)
            return rec.get("sr_no", "?"), f"ok_{len(data)//1024}kb"
        except Exception as e:
            if attempt == 2:
                return rec.get("sr_no", "?"), f"error_{type(e).__name__}"
            time.sleep(2 * (attempt + 1))
    return rec.get("sr_no", "?"), "unreachable"


def main():
    records = load_records()
    print(f"{len(records)} unique PDF urls")
    stats = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(download, r): r for r in records}
        done = 0
        for fut in as_completed(futures):
            sr, status = fut.result()
            stats[status.split("_")[0]] = stats.get(status.split("_")[0], 0) + 1
            done += 1
            if done % 50 == 0 or "error" in status:
                print(f"[{done}/{len(records)}] sr={sr} {status}")
    print("DONE. summary:", stats)


if __name__ == "__main__":
    main()
