#!/usr/bin/env python3
"""Registry-driven freshness checker: what's new per source, on a schedule.

Two kinds of entry:

* **LIST-checked** (dry-run capable) - the source exposes a cheap listing we can
  re-fetch and diff against the inventory without downloading anything. Used for
  telangana and the CBIC flat pages.
* **RE-RUN checked** - everything else. Those harvesters are idempotent and
  resumable: they dedup on `source_url` against their `inventory.jsonl`, so
  re-running one IS the freshness check. It downloads only what is new and this
  script reports the URLs it added. Maintaining a second listing implementation
  per portal would only drift out of sync with the harvester.

Usage: python3 check_sources.py --dry-run          (report only, no downloads)
       python3 check_sources.py --apply            (run harvesters, ingest new)
       python3 check_sources.py --apply --only gujarat

Blocked sources are recorded, not silently skipped - see BLOCKED below.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
STAGE = ROOT / "data" / "law" / "staging"
PY = sys.executable
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Sources that cannot be reached from the current egress. Kept visible so a
# green board is never claimed on a source nobody actually checked.
BLOCKED = {
    "west-bengal": "comtax.wb.gov.in:443 TCP-closed from current egress "
                   "(verified 2026-09-12); needs a run from an Indian host",
}

# feed -> (harvester module, cadence). Re-run checked unless a bespoke
# list-check is registered for the same name.
STATE_FEEDS = {
    "andhra-pradesh": ("harvest_ap.py", "weekly"),
    "assam": ("harvest_as.py", "weekly"),
    "chhattisgarh": ("harvest_cg.py", "weekly"),
    "delhi": ("harvest_dl.py", "weekly"),
    "gujarat": ("harvest_gj.py", "weekly"),
    "haryana": ("harvest_hr.py", "weekly"),
    "karnataka": ("harvest_ka.py", "weekly"),
    "kerala": ("harvest_kl.py", "weekly"),
    "maharashtra": ("harvest_mh.py", "weekly"),
    "odisha": ("harvest_od.py", "weekly"),
    "punjab": ("harvest_pb.py", "weekly"),
    "rajasthan": ("harvest_rj.py", "weekly"),
    "tamil-nadu": ("harvest_tn.py", "weekly"),
    "telangana": ("harvest_tgct.py", "weekly"),
    "uttar-pradesh": ("harvest_up.py", "weekly"),
    "west-bengal": ("harvest_wb.py", "weekly"),
}
CENTRAL_FEEDS = {
    "cbic_flat": ("harvest_cbic_flat.py", "daily"),
    "council": ("harvest_council_minutes.py", "monthly"),
}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, HERE / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _inv_path(feed: str) -> Path:
    return STAGE / feed / "inventory.jsonl"


def _inventory_urls(feed: str) -> set:
    urls = set()
    p = _inv_path(feed)
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                urls.add(json.loads(line)["source_url"])
            except (KeyError, json.JSONDecodeError):
                continue
    return urls


def _law_db_urls(host_fragment: str) -> set:
    """Known source_urls for a host, read from law.db (feeds with no inventory)."""
    db = ROOT / "data" / "law" / "law.db"
    if not db.exists():
        return set()
    import sqlite3
    con = sqlite3.connect(db)
    try:
        return {r[0] for r in con.execute(
            "SELECT source_url FROM documents WHERE source_url LIKE ?",
            (f"%{host_fragment}%",))}
    finally:
        con.close()


def _dead_urls(log_name: str) -> set:
    """URLs a harvester already tried and skipped as dead.

    Without this, a listing that carries 404s reports the same links as "new"
    on every run, which is noise rather than news.
    """
    p = ROOT / "data" / "law" / "logs" / f"{log_name}.log"
    if not p.exists():
        return set()
    import re
    # Greedy \S+ then backtrack to the last colon on the token: a non-greedy
    # match stops at the "https:" scheme and captures nothing useful.
    return set(re.findall(r"skip dead PDF (\S+):", p.read_text()))


# --- LIST-checked sources (dry-run capable) --------------------------------

def check_telangana() -> dict:
    tg = _load("harvest_tgct", "harvest_tgct.py")
    current, op = [], tg._session()
    for kind, url in tg.PAGES.items():
        html_text = tg.fetch(url, op).decode("utf-8", "replace")
        for row in tg.parse_grid(html_text):
            for target in row["targets"]:
                current.append(tg.row_key(url, row["idx"], target))
    known = _inventory_urls("telangana")
    return {"source": "telangana", "listed": len(current),
            "new": sorted(set(current) - known)}


def check_cbic_flat() -> dict:
    flat = _load("harvest_cbic_flat", "harvest_cbic_flat.py")
    current = []
    for kind, url in flat.LISTINGS:
        try:
            html_text = flat.fetch(url).decode("utf-8", "replace")
        except Exception as e:
            print(f"  listing dead: {url} ({type(e).__name__})", file=sys.stderr)
            continue
        current += [r["pdf_url"] for r in flat.parse_listing(html_text, url)]
    # The flat harvester keeps no inventory.jsonl - its dedup key is source_url
    # in law.db, so the "known" set has to come from there or every run would
    # re-report the whole listing as new. Links already tried and skipped as
    # dead are subtracted too, so "new" means genuinely fetchable.
    known = _law_db_urls("cbic-gst.gov.in") | _dead_urls("cbic_flat")
    return {"source": "cbic_flat", "listed": len(current),
            "new": sorted(set(current) - known)}


LIST_CHECKS = {"telangana": check_telangana, "cbic_flat": check_cbic_flat}


# --- RE-RUN checked sources ------------------------------------------------

def rerun_feed(feed: str, module: str) -> dict:
    """Re-run one harvester; report the URLs it actually added."""
    before = _inventory_urls(feed)
    t0 = time.time()
    try:
        proc = subprocess.run([PY, str(HERE / module)], timeout=3600,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    after = _inventory_urls(feed)
    return {"source": feed, "listed": len(after), "new": sorted(after - before),
            "rc": rc, "secs": round(time.time() - t0, 1)}


def registry() -> dict:
    all_feeds = {**STATE_FEEDS, **CENTRAL_FEEDS}
    reg = {name: {"cadence": cad, "module": mod, "kind": "rerun"}
           for name, (mod, cad) in all_feeds.items()}
    for name, fn in LIST_CHECKS.items():
        mod, cad = all_feeds.get(name, (None, "weekly"))
        reg[name] = {"cadence": cad, "module": mod, "kind": "list", "check": fn}
    return reg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        args.dry_run = True

    reg = registry()
    print(f"{len(reg)} feeds registered "
          f"({sum(1 for e in reg.values() if e['kind'] == 'list')} list-checked, "
          f"{sum(1 for e in reg.values() if e['kind'] == 'rerun')} re-run checked)\n")

    for name, entry in reg.items():
        if args.only and name != args.only:
            continue
        if name in BLOCKED:
            print(f"{name:16s} [{entry['cadence']}] BLOCKED - {BLOCKED[name]}")
            continue
        if entry["kind"] == "list":
            try:
                rep = entry["check"]()
            except Exception as e:
                print(f"{name:16s} CHECK FAILED {type(e).__name__}: {str(e)[:90]}")
                continue
        else:
            if not args.apply:
                n = len(_inventory_urls(name))
                print(f"{name:16s} [{entry['cadence']}] held={n} "
                      f"- re-run checked (use --apply to look for new)")
                continue
            rep = rerun_feed(name, entry["module"])
        print(f"{name:16s} [{entry['cadence']}] listed={rep['listed']} "
              f"new={len(rep['new'])}")
        for u in rep["new"][:10]:
            print(f"   + {u[:110]}")
        if len(rep["new"]) > 10:
            print(f"   … and {len(rep['new']) - 10} more")


if __name__ == "__main__":
    main()
