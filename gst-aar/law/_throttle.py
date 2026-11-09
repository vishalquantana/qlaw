#!/usr/bin/env python3
"""Per-host politeness limiter for the law harvesters.

Why: a flat 0.4s cadence is what got us blocked. `haryanatax.gov.in` answers a
burst with `RemoteDisconnected`, eSCR rate-limits by IP, and the egress proxy
throws intermittent tunnel 502s. Hammering a host that has started refusing is
how a scrape turns into a ban.

This keeps one cadence per host and moves it on evidence:

    normal    0.4s between requests   (LAW_MIN_DELAY)
    blocked   300s between requests   (LAW_BLOCK_DELAY)   <- "1 every 5 minutes"
    ceiling   1800s                   (LAW_MAX_DELAY)

Escalation: a block signal (connection reset, 403/429/5xx, timeout) sets the
host to the blocked cadence; further blocks double it up to the ceiling.
Decay: after a run of clean responses the cadence halves back toward normal, so
a host that recovers is not punished forever.

State persists to `data/law/throttle.json`, so a host that blocked us in one run
is still approached gently in the next.

Library use:
    import _throttle
    _throttle.wait(url)              # sleep as long as this host's cadence needs
    _throttle.on_error(url, exc)     # escalate if the failure looks like a block

CLI:
    python3 _throttle.py --status
    python3 _throttle.py --reset haryanatax.gov.in
    python3 _throttle.py --set haryanatax.gov.in=300
    python3 _throttle.py --relax          # drop every host back to normal

Set LAW_THROTTLE_OFF=1 to disable entirely (tests).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "law" / "throttle.json"


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


MIN_DELAY = _f("LAW_MIN_DELAY", 0.4)          # normal cadence, seconds
BLOCK_DELAY = _f("LAW_BLOCK_DELAY", 300.0)    # once a host blocks: 1 per 5 min
MAX_DELAY = _f("LAW_MAX_DELAY", 1800.0)       # ceiling after repeated blocks
DECAY_AFTER = int(_f("LAW_DECAY_AFTER", 10))  # clean responses before halving


def _disabled() -> bool:
    return os.environ.get("LAW_THROTTLE_OFF", "") not in ("", "0", "false")


def host_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).hostname or "unknown"
    except Exception:
        return "unknown"


def _load() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
        tmp.replace(STATE)
    except OSError:
        pass  # throttling must never break a harvest


def _rec(state: dict, host: str) -> dict:
    return state.setdefault(host, {"delay": MIN_DELAY, "blocks": 0,
                                   "successes": 0, "last": 0.0,
                                   "last_block": 0.0, "reason": ""})


def delay_for(host: str) -> float:
    return float(_load().get(host, {}).get("delay", MIN_DELAY))


def wait(url: str, host: str | None = None) -> float:
    """Block until this host's cadence allows the next request. Returns slept."""
    if _disabled():
        return 0.0
    host = host or host_of(url)
    state = _load()
    rec = _rec(state, host)
    delay = float(rec.get("delay", MIN_DELAY))
    last = float(rec.get("last", 0.0))
    now = time.time()
    slept = 0.0
    gap = delay - (now - last)
    if gap > 0:
        slept = gap
        time.sleep(gap)
    rec["last"] = time.time()
    _save(state)
    return slept


def is_block_error(exc: BaseException) -> bool:
    """Does this failure look like the host pushing back, rather than a bad link?"""
    # A missing document is not a block: 404/410 must not slow us down.
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (401, 403, 407, 429, 500, 502, 503, 504,
                            520, 521, 522, 523, 524, 525, 526)
    if isinstance(exc, urllib.error.URLError):
        return is_block_error(exc.reason) if isinstance(exc.reason, BaseException) else True
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                        ConnectionRefusedError, socket.timeout, TimeoutError,
                        socket.gaierror, BrokenPipeError)):
        return True
    name = type(exc).__name__
    if name in ("RemoteDisconnected", "IncompleteRead", "BadStatusLine"):
        return True
    text = str(exc).lower()
    return any(s in text for s in ("too many requests", "rate limit",
                                   "temporarily unavailable", "connection reset",
                                   "remote end closed", "timed out"))


def on_error(url: str, exc: BaseException | None = None,
             host: str | None = None) -> float:
    """Escalate the host's cadence if this failure looks like blocking."""
    if _disabled():
        return 0.0
    if exc is not None and not is_block_error(exc):
        return delay_for(host or host_of(url))
    host = host or host_of(url)
    state = _load()
    rec = _rec(state, host)
    cur = float(rec.get("delay", MIN_DELAY))
    new = BLOCK_DELAY if cur < BLOCK_DELAY else min(cur * 2.0, MAX_DELAY)
    rec.update(delay=new, blocks=int(rec.get("blocks", 0)) + 1,
               successes=0, last_block=time.time(),
               reason=type(exc).__name__ if exc is not None else "unknown")
    _save(state)
    print(f"  [throttle] {host}: blocking signal ({rec['reason']}) -> "
          f"{new:.0f}s between requests", file=sys.stderr)
    return new


def on_success(url: str, host: str | None = None) -> float:
    """Decay the host's cadence back toward normal after sustained success."""
    if _disabled():
        return 0.0
    host = host or host_of(url)
    state = _load()
    rec = _rec(state, host)
    cur = float(rec.get("delay", MIN_DELAY))
    n = int(rec.get("successes", 0)) + 1
    if cur > MIN_DELAY and n >= DECAY_AFTER:
        cur = max(MIN_DELAY, cur / 2.0)
        n = 0
    rec.update(delay=cur, successes=n)
    _save(state)
    return cur


def status() -> list[tuple[str, float, int, str]]:
    state = _load()
    rows = []
    for host, rec in sorted(state.items()):
        d = float(rec.get("delay", MIN_DELAY))
        if d <= MIN_DELAY and not rec.get("blocks"):
            continue
        rows.append((host, d, int(rec.get("blocks", 0)),
                     rec.get("reason", "")))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", metavar="HOST")
    ap.add_argument("--set", metavar="HOST=SECONDS")
    ap.add_argument("--relax", action="store_true",
                    help="drop every host back to the normal cadence")
    args = ap.parse_args()

    state = _load()
    if args.relax:
        for host, rec in state.items():
            rec.update(delay=MIN_DELAY, blocks=0, successes=0, reason="")
        _save(state)
        print(f"relaxed {len(state)} hosts to {MIN_DELAY}s")
        return
    if args.reset:
        state.pop(args.reset, None)
        _save(state)
        print(f"reset {args.reset}")
        return
    if args.set:
        host, _, secs = args.set.partition("=")
        _rec(state, host).update(delay=float(secs), reason="manual")
        _save(state)
        print(f"{host} -> {float(secs):.0f}s")
        return

    print(f"normal {MIN_DELAY}s · blocked {BLOCK_DELAY}s · ceiling {MAX_DELAY}s")
    rows = status()
    if not rows:
        print("all hosts at the normal cadence")
    for host, d, blocks, reason in rows:
        print(f"  {host:34s} {d:>7.0f}s  blocks={blocks:<3} last={reason}")


if __name__ == "__main__":
    main()
