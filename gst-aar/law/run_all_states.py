#!/usr/bin/env python3
"""Drive every reachable state harvester to completion.

Why a driver: 14 feeds x hundreds of PDFs each at a 0.4s throttle is 30-60 min
of wall clock. Each harvester skips source_urls already in its inventory.jsonl,
so a re-run is safe; this driver runs passes until every feed stops adding.

Egress note (2026-09-12): traffic goes through a sandbox proxy that returns
intermittent 502 tunnel errors, so single failures are expected and are absorbed
by the per-harvester retry plus the multi-pass loop here.

West Bengal is deliberately EXCLUDED, not silently skipped: comtax.wb.gov.in:443
is TCP-closed from the current egress (verified 2026-09-12). Its 410 held files
stay; it needs a run from an Indian host.

Usage: python3 run_all_states.py            (all reachable feeds, 3 passes max)
       python3 run_all_states.py --only gujarat
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LOGS = ROOT / "data" / "law" / "logs"
PY = sys.executable
MAX_PASSES = 3
WORKERS = 3

FEEDS = [
    ("gujarat", "harvest_gj.py"),
    ("maharashtra", "harvest_mh.py"),
    ("uttar-pradesh", "harvest_up.py"),
    ("haryana", "harvest_hr.py"),
    ("assam", "harvest_as.py"),
    ("punjab", "harvest_pb.py"),
    ("delhi", "harvest_dl.py"),
    ("odisha", "harvest_od.py"),
    ("rajasthan", "harvest_rj.py"),
    ("karnataka", "harvest_ka.py"),
    ("kerala", "harvest_kl.py"),
    ("tamil-nadu", "harvest_tn.py"),
    ("chhattisgarh", "harvest_cg.py"),
    ("telangana", "harvest_tgct.py"),
]

EXCLUDED = {
    "west-bengal": "comtax.wb.gov.in:443 unreachable from current egress "
                   "(TCP closed, verified 2026-09-12); needs an Indian host",
}


def inv_count(feed: str) -> int:
    p = ROOT / "data" / "law" / "staging" / feed / "inventory.jsonl"
    if not p.exists():
        return 0
    return sum(1 for line in p.open() if line.strip())


def run_feed(feed: str, module: str, pass_no: int, env: dict | None = None) -> dict:
    log = LOGS / f"{feed}.log"
    before = inv_count(feed)
    start_size = log.stat().st_size if log.exists() else 0
    t0 = time.time()
    with log.open("a") as fh:
        fh.write(f"\n===== pass {pass_no} start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        fh.flush()
        try:
            proc = subprocess.run([PY, str(HERE / module)], stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=3600, env=env)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    after = inv_count(feed)
    # A harvester that cannot reach its index prints "index dead" and still
    # exits 0, so added==0 is NOT proof of completion. Detect it explicitly.
    tail = log.read_text()[start_size:] if log.exists() else ""
    index_dead = "index dead" in tail
    return {"feed": feed, "module": module, "rc": rc, "before": before,
            "after": after, "added": after - before, "secs": round(time.time() - t0, 1),
            "index_dead": index_dead}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="",
                    help="comma-separated feed names to run")
    ap.add_argument("--skip", default="",
                    help="comma-separated feed names to skip (e.g. a feed whose "
                         "remaining links are all dead upstream)")
    ap.add_argument("--min-delay", type=float, default=None,
                    help="normal seconds between requests (default 0.4)")
    ap.add_argument("--block-delay", type=float, default=None,
                    help="seconds between requests once a host blocks "
                         "(default 300 = one every 5 minutes)")
    ap.add_argument("--max-delay", type=float, default=None,
                    help="ceiling after repeated blocks (default 1800)")
    args = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)

    # Harvesters read these from the environment, so the cadence is a run-time
    # knob rather than a constant baked into 20 files.
    env = dict(os.environ)
    for flag, var in (("min_delay", "LAW_MIN_DELAY"),
                      ("block_delay", "LAW_BLOCK_DELAY"),
                      ("max_delay", "LAW_MAX_DELAY")):
        val = getattr(args, flag)
        if val is not None:
            env[var] = str(val)

    only = {s for s in args.only.split(",") if s}
    skip = {s for s in args.skip.split(",") if s}
    feeds = [(f, m) for f, m in FEEDS
             if (not only or f in only) and f not in skip]
    pending = list(feeds)
    summary: list[dict] = []
    print(f"driving {len(pending)} feeds, max {MAX_PASSES} passes, {WORKERS} workers", flush=True)

    for pass_no in range(1, MAX_PASSES + 1):
        if not pending:
            break
        print(f"\n### pass {pass_no}: {len(pending)} feeds", flush=True)
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(run_feed, f, m, pass_no, env): f for f, m in pending}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                flag = " INDEX-DEAD" if r["index_dead"] else ""
                print(f"  {r['feed']:16s} rc={r['rc']:>3} +{r['added']:>4} "
                      f"(total {r['after']:>4}) {r['secs']:>7.1f}s{flag}", flush=True)
        summary.extend(results)
        # Retry when the feed added rows, exited non-zero, or never reached its
        # index (a silent failure that still exits 0).
        pending = [(f, m) for f, m in pending
                   if any(r["feed"] == f and (r["rc"] != 0 or r["added"] > 0
                                              or r["index_dead"])
                          for r in results)]

    totals = {}
    for r in summary:
        t = totals.setdefault(r["feed"], {"added": 0, "final": 0})
        t["added"] += r["added"]
        t["final"] = r["after"]
    print("\n=== final per-feed inventory ===", flush=True)
    for feed, t in sorted(totals.items(), key=lambda x: -x[1]["final"]):
        print(f"  {feed:16s} +{t['added']:>4} added, {t['final']:>4} total")
    for feed, why in EXCLUDED.items():
        print(f"  {feed:16s} EXCLUDED — {why}")
    print(f"  grand total files: {sum(t['final'] for t in totals.values()):,}")

    # Which hosts pushed back, and how hard we are now approaching them.
    try:
        import importlib.util as _ilu
        _s = _ilu.spec_from_file_location("_throttle", HERE / "_throttle.py")
        thr = _ilu.module_from_spec(_s)
        _s.loader.exec_module(thr)
        rows = thr.status()
        if rows:
            print("\n=== hosts that pushed back ===")
            for host, delay, blocks, reason in rows:
                print(f"  {host:34s} {delay:>7.0f}s between requests "
                      f"(blocks={blocks}, last={reason})")
        else:
            print("\nno host showed a blocking signal this run")
    except Exception as e:
        print(f"\n(throttle status unavailable: {type(e).__name__})")

    out = ROOT / "data" / "law" / "logs" / "run_all_states.summary.json"
    out.write_text(json.dumps({"runs": summary, "totals": totals,
                               "excluded": EXCLUDED}, indent=2))
    print(f"\nsummary: {out}", flush=True)


if __name__ == "__main__":
    main()
