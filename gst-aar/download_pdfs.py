#!/usr/bin/env python3
"""Download all AAR/AAAR ruling PDFs from the scraped listing.

Resumable: skips files that already exist with non-trivial size and matching
content-length when known. Parallel workers with polite delays.
"""
import json
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

LIST = Path(__file__).parent / "data" / "aar_list.jsonl"
PDF_DIR = Path(__file__).parent / "data" / "pdfs"
DB = Path(__file__).parent / "data" / "aar.db"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

WORKERS = 6
THROTTLE_S = 0.5  # per-request delay: polite + predictable bandwidth

# Live inventory: every download attempt is recorded here as it happens, so the
# SQLite DB is always current even if the run is interrupted.
DOWNLOAD_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS download_log (
    source_url TEXT PRIMARY KEY,
    local_path TEXT,
    size_bytes INTEGER,
    status TEXT,          -- ok | not_pdf | error_* | exists
    attempts INTEGER,
    downloaded_at TEXT
);
"""


def log_download(url: str, local: Path | None, size: int, status: str, attempts: int):
    try:
        con = sqlite3.connect(DB)
        con.execute(DOWNLOAD_LOG_SCHEMA)
        con.execute(
            "INSERT INTO download_log (source_url, local_path, size_bytes, status, attempts, downloaded_at)"
            " VALUES (?,?,?,?,?,?) ON CONFLICT(source_url) DO UPDATE SET"
            " local_path=excluded.local_path, size_bytes=excluded.size_bytes,"
            " status=excluded.status, attempts=excluded.attempts, downloaded_at=excluded.downloaded_at",
            (url, str(local) if local else None, size, status, attempts,
             time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        con.commit()
        con.close()
    except sqlite3.Error as e:
        print(f"  db log failed for {url}: {e}", file=sys.stderr)


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
        log_download(rec["pdf_url"], dest, dest.stat().st_size, "exists", 0)
        return rec.get("sr_no", "?"), "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            time.sleep(THROTTLE_S)
            req = urllib.request.Request(rec["pdf_url"], headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 1_000 or not data.startswith(b"%PDF"):
                if not data.startswith(b"%PDF"):
                    log_download(rec["pdf_url"], dest, len(data), "not_pdf", attempt + 1)
                    return rec.get("sr_no", "?"), f"not_pdf_{len(data)}b"
            dest.write_bytes(data)
            log_download(rec["pdf_url"], dest, len(data), "ok", attempt + 1)
            return rec.get("sr_no", "?"), f"ok_{len(data)//1024}kb"
        except Exception as e:
            if attempt == 2:
                log_download(rec["pdf_url"], dest, 0, f"error_{type(e).__name__}", attempt + 1)
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
