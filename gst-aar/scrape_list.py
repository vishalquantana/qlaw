#!/usr/bin/env python3
"""Scrape the GST Council AAR/AAAR order listing (all pages) into JSONL.

Source: https://www.gstcouncil.gov.in/authority-for-advance-ruling?page=N
Columns: Sr. No. | Applicant | State/UT | Brief of Order | Order No & Date | Download | Category
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://www.gstcouncil.gov.in/authority-for-advance-ruling"
OUT = Path(__file__).parent / "data" / "aar_list.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

CELL_ORDER = ["sr_no", "applicant", "state", "brief", "order_no_date", "pdf_path", "category"]


def fetch(url: str, retries: int = 3) -> str:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i+1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def clean(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text).replace("&amp;", "&").split())


def parse_page(html: str) -> list[dict]:
    rows = []
    # main listing table rows
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 7:
            continue
        rec = {}
        pdf_m = re.search(r'href="(/sites/default/files/[^"]+\.pdf)"', tds[5])
        for key, cell in zip(CELL_ORDER, tds[:7]):
            rec[key] = clean(cell)
        rec["pdf_url"] = ("https://www.gstcouncil.gov.in" + pdf_m.group(1)) if pdf_m else None
        rec["pdf_path"] = pdf_m.group(1) if pdf_m else None
        rows.append(rec)
    return rows


def main(start_page: int = 0, max_page: int | None = None):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen_urls = set()
    total = 0
    page = start_page
    with OUT.open("a") as f:
        while True:
            url = BASE if page == 0 else f"{BASE}?page={page}"
            html = fetch(url)
            rows = parse_page(html)
            new = [r for r in rows if r["pdf_url"] and r["pdf_url"] not in seen_urls]
            for r in new:
                r["page"] = page
                seen_urls.add(r["pdf_url"])
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            total += len(new)
            print(f"page {page}: {len(rows)} rows, {len(new)} new (running total {total})")
            if not rows and page > 0:
                print("empty page, stopping")
                break
            page += 1
            if max_page is not None and page > max_page:
                break
            time.sleep(0.4)
    print(f"DONE: {total} rulings -> {OUT}")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    maxp = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(start, maxp)
