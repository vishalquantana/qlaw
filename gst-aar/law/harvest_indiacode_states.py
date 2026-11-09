#!/usr/bin/env python3
"""Harvest State GST Acts (and State GST notifications) from India Code.

The corpus holds 0 of the 28 State GST Acts. India Code carries all of them: each
state/UT is a community, and each community has the same collection layout as
CENTRAL (Acts, Section, Notification, Circular, Rule, Form, ...). Searching a
state's `Acts` collection for "Goods and Services Tax" returns its SGST Act —
verified for Goa ("THE GOA GOODS AND SERVICES TAX ACT, 2017"), Tripura,
Uttarakhand, Himachal Pradesh, Tamil Nadu, Andhra Pradesh and others.

Text comes from the item's **TEXT** bundle (India Code pre-extracts it), so no
PDF download and no OCR.

Usage: python3 harvest_indiacode_states.py                 (all states, resumable)
       python3 harvest_indiacode_states.py --only goa,tripura
       python3 harvest_indiacode_states.py --notifications  (also pull state GST notifications)
"""
from __future__ import annotations

import argparse
import hashlib
import html
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
OUT = ROOT / "data" / "law" / "indiacode"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "state_acts.jsonl"

BASE = "https://indiacode.gov.in/server/api"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Accept": "application/json"}
PAGE = 100
# Deliberately tolerant. India Code's own titles carry typos and singular forms:
#   Kerala  -> "The Kerala State Gooda and Services Tax Act, 2017"   ("Gooda")
#   Sikkim  -> "THE SIKKIM GOODS AND SERVICE TAX ACT,2017"           ("Service")
# A strict "Goods and Services Tax" misses both.
GST_RE = re.compile(r"(?:goods?|gooda)\s*(?:and|&)\s*servic(?:e|es)\s*tax", re.I)
# A state's `Notification` collection is NOT GST-specific — Madhya Pradesh's
# includes electricity-board appointments and panchayat matters. So notifications
# are filtered on their CONTENT, not their title. Sampled yield: MP 36%,
# Jharkhand 88% of the collection.
GST_CONTENT_RE = re.compile(
    r"goods\s*(?:and|&)\s*servic|\bCGST\b|\bSGST\b|\bIGST\b|state\s+tax|central\s+tax",
    re.I)

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", HERE / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)


def _load_law_db():
    spec = importlib.util.spec_from_file_location("law_db", HERE / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_json(url: str, retries: int = 3) -> dict:
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


def get_bytes(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        _thr.wait(url)
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}),
                    timeout=120) as r:
                blob = r.read()
            _thr.on_success(url)
            return blob
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def field(md: dict, key: str) -> str:
    v = md.get(key)
    return v[0]["value"] if v else ""


def communities() -> list[tuple[str, str]]:
    d = get_json(f"{BASE}/core/communities?size=60")
    return [(c.get("name", ""), c["uuid"])
            for c in d["_embedded"]["communities"]]


def collections_of(community_uuid: str) -> dict[str, str]:
    d = get_json(f"{BASE}/core/communities/{community_uuid}/collections?size=60")
    return {c.get("name", ""): c["uuid"] for c in d["_embedded"].get("collections", [])}


def search(collection_uuid: str, query: str, page: int = 0) -> dict:
    url = (f"{BASE}/discover/search/objects?scope={collection_uuid}"
           f"&query={urllib.parse.quote(query)}&size={PAGE}&page={page}")
    return get_json(url)


def text_of(item_uuid: str) -> str:
    """India Code pre-extracts act text into the TEXT bundle."""
    try:
        bd = get_json(f"{BASE}/core/items/{item_uuid}/bundles")
    except Exception:
        return ""
    for b in bd["_embedded"]["bundles"]:
        if b["name"] != "TEXT":
            continue
        bs = get_json(b["_links"]["bitstreams"]["href"])
        for x in bs["_embedded"]["bitstreams"]:
            try:
                raw = get_bytes(x["_links"]["content"]["href"])
                return raw.decode("utf-8", "replace")
            except Exception:
                continue
    return ""


def clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()


def harvest_state(name: str, community_uuid: str, cols: dict[str, str],
                  law_db, con, seen: set, notifications: bool) -> int:
    targets = [("Acts", "sgst_act")]
    if notifications:
        targets.append(("Notification", "sgst_notification"))
    added = 0
    for coll_name, kind in targets:
        coll = cols.get(coll_name)
        if not coll:
            continue
        page, kept = 0, 0
        while True:
            try:
                d = search(coll, "Goods and Services Tax", page)
            except Exception as e:
                print(f"    {name}/{coll_name} page {page}: {type(e).__name__}",
                      file=sys.stderr)
                break
            objs = d["_embedded"]["searchResult"]["_embedded"]["objects"]
            if not objs:
                break
            for o in objs:
                ind = o["_embedded"]["indexableObject"]
                md = ind.get("metadata", {})
                title = clean(field(md, "dc.title") or ind.get("name", ""))
                uuid = ind.get("uuid")
                url = f"{BASE}/core/items/{uuid}"
                if url in seen:
                    continue
                # Both Acts and Notifications carry a TEXT bundle on India Code.
                # Notifications are often scans, so a very short extraction is
                # treated as "no text" rather than stored as if it were content.
                body = clean(text_of(uuid))
                if len(body) < 200:
                    body = ""
                if kind == "sgst_act":
                    if not GST_RE.search(title):
                        seen.add(url)
                        continue
                elif not (GST_CONTENT_RE.search(body) or GST_RE.search(title)):
                    # a general gazette notification, not a GST one
                    seen.add(url)
                    continue
                # marked seen once fetched, so a resume does not re-fetch it
                seen.add(url)
                doc_id = law_db.upsert_document(con, {
                    "source_url": url, "kind": kind,
                    "title": title[:300],
                    "number": clean(field(md, "dc.identifier.act_number")
                                    or field(md, "dc.identifier.order_number"))[:60],
                    "pub_date": clean(field(md, "dc.date.act_year")
                                      or field(md, "dc.date.issued"))[:10],
                    "local_path": "",
                    "sha256": hashlib.sha256((body or title).encode()).hexdigest(),
                    "body": body})
                # SGST is state-specific, and India Code notification titles do
                # NOT carry the state name (e.g. "Notification 52 S.O. No. 52- 77
                # - TAX.pdf"), so the state has to be recorded explicitly or the
                # document is unattributable.
                con.execute("INSERT OR IGNORE INTO law_tags (doc_id, tag) VALUES (?,?)",
                            (doc_id, f"state:{name}"))
                kept += 1
                if kind == "sgst_act" and body:
                    with LOG.open("a") as fh:
                        fh.write(json.dumps({"state": name, "title": title,
                                             "uuid": uuid, "chars": len(body)}) + "\n")
            total = d["_embedded"]["searchResult"]["page"]["totalElements"]
            page += 1
            if page * PAGE >= total or page > 20:
                break
        con.commit()
        added += kept
        if kept:
            print(f"    {name:24s} {coll_name:13s} +{kept}")
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated state names (substring)")
    ap.add_argument("--notifications", action="store_true",
                    help="also harvest state GST notifications (metadata only)")
    args = ap.parse_args()

    law_db = _load_law_db()
    con = law_db.init_db()
    con.executescript("""CREATE TABLE IF NOT EXISTS law_tags (
        id INTEGER PRIMARY KEY,
        doc_id INTEGER NOT NULL REFERENCES documents(id),
        tag TEXT NOT NULL, UNIQUE(doc_id, tag));""")
    seen = {r[0] for r in con.execute(
        "SELECT source_url FROM documents WHERE kind IN ('sgst_act','sgst_notification')")}
    print(f"already held: {len(seen)}")

    only = [s.strip().lower() for s in args.only.split(",") if s.strip()]
    comms = communities()
    print(f"communities: {len(comms)}\n")

    grand = 0
    for name, uuid in comms:
        if name.upper() == "CENTRAL":
            continue
        if only and not any(o in name.lower() for o in only):
            continue
        try:
            cols = collections_of(uuid)
        except Exception as e:
            print(f"  {name}: collections failed {type(e).__name__}", file=sys.stderr)
            continue
        n = harvest_state(name, uuid, cols, law_db, con, seen, args.notifications)
        grand += n
    con.close()
    print(f"\ndone: {grand} documents added")


if __name__ == "__main__":
    main()
