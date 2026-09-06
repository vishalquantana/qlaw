#!/usr/bin/env python3
"""Registry-driven freshness checker: what's new per source, on a schedule.

Each entry knows how to LIST current items and how to FETCH new ones, so the
weekly/daily loop is: list → diff vs inventory → download → extract → embed.
Methods documented in SOURCES.md.

Usage: python3 check_sources.py --dry-run        (report only, no downloads)
       python3 check_sources.py --apply          (download new items too)
       python3 check_sources.py --dry-run --only telangana
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _inventory_urls(path: Path) -> set:
    urls = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                urls.add(json.loads(line)["source_url"])
            except (KeyError, json.JSONDecodeError):
                continue
    return urls


def check_telangana():
    tg = _load("harvest_tgct", "harvest_tgct.py")
    current, op = [], tg._session()
    for kind, url in tg.PAGES.items():
        html_text = tg.fetch(url, op).decode("utf-8", "replace")
        for row in tg.parse_grid(html_text):
            for target in row["targets"]:
                current.append(tg.row_key(url, row["idx"], target))
    known = _inventory_urls(ROOT / "data" / "law" / "staging" / "telangana" / "inventory.jsonl")
    return {"source": "telangana", "listed": len(current),
            "new": sorted(set(current) - known)}


def check_cbic_flat():
    flat = _load("harvest_cbic_flat", "harvest_cbic_flat.py")
    current = []
    for kind, url in flat.LISTINGS:
        try:
            html_text = flat.fetch(url).decode("utf-8", "replace")
        except Exception as e:
            print(f"  listing dead: {url} ({type(e).__name__})", file=sys.stderr)
            continue
        current += [r["pdf_url"] for r in flat.parse_listing(html_text, url)]
    sys.path.insert(0, str(ROOT.parent / "tests"))
    from gst_aar_law_shim import law_db
    con = law_db.init_db()
    known = {r[0] for r in con.execute(
        "SELECT source_url FROM documents WHERE source_url LIKE '%cbic-gst.gov.in%'")}
    return {"source": "cbic_flat", "listed": len(current),
            "new": sorted(set(current) - known)}


REGISTRY = {
    "telangana": {"check": check_telangana, "fetch": "harvest_tgct.main",
                  "cadence": "weekly"},
    "cbic_flat": {"check": check_cbic_flat, "fetch": "harvest_cbic_flat.main",
                  "cadence": "daily"},
    # Next to wire: council_minutes, escr (session), gstat (session), states...
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        args.dry_run = True
    for name, entry in REGISTRY.items():
        if args.only and name != args.only:
            continue
        try:
            rep = entry["check"]()
        except Exception as e:
            print(f"{name}: CHECK FAILED {type(e).__name__}: {str(e)[:120]}")
            continue
        print(f"{name} [{entry['cadence']}]: listed={rep['listed']} new={len(rep['new'])}")
        for u in rep["new"][:10]:
            print(f"   + {u[:110]}")
        if len(rep["new"]) > 10:
            print(f"   … and {len(rep['new']) - 10} more")
        if args.apply and rep["new"]:
            mod_name, fn = entry["fetch"].split(".")
            mod = _load(mod_name, mod_name + ".py")
            print(f"  fetching via {entry['fetch']} …")
            getattr(mod, fn)()


if __name__ == "__main__":
    main()
