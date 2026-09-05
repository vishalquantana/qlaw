#!/usr/bin/env python3
"""Stream A: harvest GST acts/rules/sections from taxinformation.cbic.gov.in.

Pattern follows gst-aar/scrape_list.py (stdlib urllib, retry, UA header).
PoC: python3 harvest_cbic_api.py --limit 5 (verifies token + 1 page before full pull).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://taxinformation.cbic.gov.in"
ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "acts"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _load_law_db():
    # gst-aar is hyphenated so this file never lives in an importable
    # package when run directly; load law_db the same way tests do.
    spec = importlib.util.spec_from_file_location(
        "law_db", Path(__file__).parent / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _req(url: str, token: str | None = None, data: bytes | None = None,
         retries: int = 3) -> bytes:
    headers = dict(UA)
    if token:
        headers.update(auth_headers(token))
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_token(base: str = BASE) -> str:
    raw = _req(base + "/api/authenticate-token", data=b"{}")
    payload = json.loads(raw.decode("utf-8", "replace"))
    for key in ("id_token", "token", "access_token"):
        if payload.get(key):
            return payload[key]
    raise RuntimeError(f"no token in auth response keys: {sorted(payload)}")


def fetch_paged(base: str, token: str, path: str, page: int = 0,
                size: int = 50) -> list[dict]:
    sep = "&" if "?" in path else "?"
    raw = _req(f"{base}{path}{sep}page={page}&size={size}", token)
    payload = json.loads(raw.decode("utf-8", "replace"))
    if isinstance(payload, list):
        return payload
    for key in ("content", "data", "result"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def normalize_acts(rows: list[dict]) -> list[dict]:
    docs = []
    for r in rows:
        name = r.get("actName") or r.get("name") or ""
        if not name:
            continue
        # Live API keys rows by `id` (brief fixture uses `actId`); accept both.
        act_id = r.get("actId") or r.get("id") or ""
        docs.append({
            "source_url": f"{BASE}/content-page/explore-act/{act_id}/1000001",
            "kind": "act",
            "title": name,
            "number": "",
            "pub_date": r.get("issueDt", ""),
            "local_path": "",
            "sha256": hashlib.sha256(
                json.dumps(r, sort_keys=True).encode()).hexdigest(),
            "body": json.dumps(r, ensure_ascii=False),
        })
    return docs


def main(limit: int = 0):
    OUT.mkdir(parents=True, exist_ok=True)
    token = get_token()
    seen, total, page = set(), 0, 0
    law_db = _load_law_db()
    con = law_db.init_db()
    while True:
        rows = fetch_paged(BASE, token, "/api/cbic-act-msts", page)
        if not rows:
            break
        new_in_page = 0
        for doc in normalize_acts(rows):
            if doc["source_url"] in seen:
                continue
            seen.add(doc["source_url"])
            law_db.upsert_document(con, doc)
            total += 1
            new_in_page += 1
            if limit and total >= limit:
                print(f"PoC slice done: {total} acts")
                return
        print(f"page {page}: {len(rows)} rows (total {total})")
        if new_in_page == 0:
            # API ignores page/size (repeats the same rows): no progress = done.
            print(f"no new rows on page {page}, stopping")
            break
        page += 1
        time.sleep(0.4)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    main(**vars(ap.parse_args()))
