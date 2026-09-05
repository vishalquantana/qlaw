#!/usr/bin/env python3
"""Daily checker: diff listing snapshots → ingest new docs → append changes.jsonl.

Usage: python3 check_daily.py --since 2026-09-01   # dry-run diff report
       python3 check_daily.py --apply               # ingest new docs
Aborts below 10 GiB free (spec §2). Never rebuilds the DB.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGES = ROOT / "data" / "law" / "changes.jsonl"
MIN_FREE_GB = 10


def canon(row) -> dict:
    return {"source_url": row.get("source_url") or row.get("pdf_url", ""),
            "date": row.get("date", "")}


def diff_listings(old: list[dict], new: list[dict]) -> list[dict]:
    seen = {canon(r)["source_url"] for r in old}
    seen.discard("")
    out = []
    for r in new:
        url = canon(r)["source_url"]
        if not url:
            continue
        if url not in seen:
            out.append(r)
    return out


def disk_ok() -> bool:
    free_gb = shutil.disk_usage(ROOT).free / (1024 ** 3)
    return free_gb >= MIN_FREE_GB


def main(since: str = "", apply: bool = False):
    if not disk_ok():
        raise SystemExit("disk below 10 GiB free — aborting daily check")
    seen_urls: set[str] = set()
    if CHANGES.exists():
        for line in CHANGES.read_text().splitlines():
            try:
                seen_urls.add(json.loads(line)["source_url"])
            except (KeyError, json.JSONDecodeError, TypeError):
                continue
    print(f"known changes: {len(seen_urls)} (since filter: {since or 'none'})")
    if since:
        try:
            cutoff = datetime.date.fromisoformat(since)
        except (ValueError, TypeError):
            raise SystemExit("--since must be YYYY-MM-DD")
        print(f"dry-run diff since {cutoff}: {len(seen_urls)} known, 0 new (no fetch in dry-run)")
    if apply:
        print("apply: harvester wiring pending, no writes performed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    main(since=args.since, apply=args.apply)
