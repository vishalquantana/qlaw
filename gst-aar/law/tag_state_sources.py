#!/usr/bin/env python3
"""Attribute India Code state documents to their state.

India Code notification titles do NOT carry the state name — a real example is
"Notification 52 S.O. No. 52- 77 - TAX.pdf" — so a document harvested from a
state community is unattributable from its own row. SGST is state-specific, so
that matters.

This walks each state community's collections, collects the item UUIDs, and tags
the matching documents `state:<name>` in law_tags. It reads the collection
listings (about 30 paginated calls for the whole corpus) rather than the item API
(one call per document), so it is cheap.

Usage: python3 tag_state_sources.py --check
       python3 tag_state_sources.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW_DB = ROOT / "data" / "law" / "law.db"
BASE = "https://indiacode.gov.in/server/api"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Accept": "application/json"}
KINDS = ("sgst_act", "sgst_notification")

try:
    import _throttle as _thr
except ImportError:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", HERE / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)


def get(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        _thr.wait(url)
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=90) as r:
                blob = r.read()
            _thr.on_success(url)
            return json.loads(blob)
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def community_uuids_by_state() -> list[tuple[str, str]]:
    d = get(f"{BASE}/core/communities?size=60")
    return [(c.get("name", ""), c["uuid"]) for c in d["_embedded"]["communities"]
            if c.get("name", "").upper() != "CENTRAL"]


def collection_item_uuids(collection_uuid: str, cap: int = 40) -> set[str]:
    uuids, page = set(), 0
    while page < cap:
        d = get(f"{BASE}/discover/search/objects?scope={collection_uuid}"
                f"&size=100&page={page}")
        sr = d["_embedded"]["searchResult"]
        objs = sr["_embedded"]["objects"]
        if not objs:
            break
        for o in objs:
            u = o["_embedded"]["indexableObject"].get("uuid")
            if u:
                uuids.add(u)
        page += 1
        if page * 100 >= sr["page"]["totalElements"]:
            break
    return uuids


def main(check: bool = False) -> None:
    con = __import__("sqlite3").connect(LAW_DB)
    con.executescript("""CREATE TABLE IF NOT EXISTS law_tags (
        id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL,
        tag TEXT NOT NULL, UNIQUE(doc_id, tag));""")
    # key by the item UUID, which is the last path segment of the source_url
    docs: dict[str, int] = {}
    for url, i in con.execute(
            f"SELECT source_url, id FROM documents WHERE kind IN {KINDS}"):
        docs[url.rstrip("/").rsplit("/", 1)[-1]] = i
    print(f"state documents: {len(docs):,}")

    tagged = 0
    for name, cuuid in community_uuids_by_state():
        try:
            cols = get(f"{BASE}/core/communities/{cuuid}/collections?size=60")
        except Exception as e:
            print(f"  {name}: {type(e).__name__}", file=sys.stderr)
            continue
        ids: set[str] = set()
        for c in cols["_embedded"].get("collections", []):
            if c.get("name") in ("Acts", "Notification"):
                ids |= collection_item_uuids(c["uuid"])
        hits = [docs[u] for u in ids if u in docs]
        if not hits:
            continue
        print(f"  {name:34s} {len(hits):>5} documents")
        if not check:
            con.executemany(
                "INSERT OR IGNORE INTO law_tags (doc_id, tag) VALUES (?,?)",
                [(i, f"state:{name}") for i in hits])
            con.commit()
        tagged += len(hits)

    if check:
        print(f"\n(dry run — would tag {tagged} documents)")
    else:
        n = con.execute("SELECT COUNT(DISTINCT doc_id) FROM law_tags"
                        " WHERE tag LIKE 'state:%'").fetchone()[0]
        print(f"\ntagged {tagged}; documents now carrying a state tag: {n:,}")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    main(check=args.check)
