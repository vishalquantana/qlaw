#!/usr/bin/env python3
"""Incremental scraper for GST Council AAR/AAAR listings.

Scrapes page 0, 1, ... until all rulings on a page are already known in
data/aar_list.jsonl, appending newly found rulings and reporting them.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
LIST_FILE = DATA_DIR / "aar_list.jsonl"

sys.path.insert(0, str(HERE))
from scrape_list import BASE, fetch, parse_page

def main():
    if not LIST_FILE.exists():
        print(f"Error: {LIST_FILE} not found.")
        sys.exit(1)

    existing_urls = set()
    with LIST_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                url = data.get("pdf_url") or data.get("pdf_path")
                if url:
                    existing_urls.add(url)
            except Exception:
                pass

    print(f"Loaded {len(existing_urls):,} existing ruling URLs from {LIST_FILE.name}")

    page = 0
    all_new_rows = []
    consecutive_seen = 0

    while True:
        url = BASE if page == 0 else f"{BASE}?page={page}"
        print(f"Checking page {page} ({url})...")
        try:
            html = fetch(url)
            rows = parse_page(html)
        except Exception as e:
            print(f"  Failed to fetch page {page}: {e}")
            break

        if not rows:
            print(f"  Empty page {page}, stopping.")
            break

        new_on_page = []
        for r in rows:
            p_url = r.get("pdf_url")
            if p_url and p_url not in existing_urls:
                r["page"] = page
                existing_urls.add(p_url)
                new_on_page.append(r)
                consecutive_seen = 0
            else:
                consecutive_seen += 1

        all_new_rows.extend(new_on_page)
        print(f"  Page {page}: {len(rows)} rows found, {len(new_on_page)} are brand new.")

        # If all items on this page are already known, we have reached the backfill point
        if not new_on_page and consecutive_seen >= 10:
            print(f"Reached existing records (consecutive seen: {consecutive_seen}). Halting scrape.")
            break

        page += 1
        time.sleep(0.5)

    if all_new_rows:
        print(f"\nAppending {len(all_new_rows)} new rulings to {LIST_FILE.name}...")
        with LIST_FILE.open("a", encoding="utf-8") as f:
            for r in all_new_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("Done appending to list.")
        print("\n--- Summary of New Rulings ---")
        for idx, r in enumerate(all_new_rows[:10], 1):
            print(f"{idx}. [{r.get('order_no_date')}] ({r.get('state')}) {r.get('applicant')[:70]}...")
        if len(all_new_rows) > 10:
            print(f"... and {len(all_new_rows) - 10} more.")
    else:
        print("\nNo new rulings found. Database is completely up-to-date with GST Council portal.")

if __name__ == "__main__":
    main()
