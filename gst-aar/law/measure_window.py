#!/usr/bin/env python3
"""Measure whether the 9,000-character prompt window is costing us outcomes.

The questions pass sends `text[:9000]`. But 78% of rulings are longer than that
(median 18,458 chars), and **92% of the question rows with an unknown outcome come
from a ruling that was truncated**. That correlation is suggestive, not proof — the
outcome might simply not be stated, or the model might not extract it when it is.

This runs the same extraction over the SAME rulings with a wider window and compares,
so the re-run decision rests on a measurement rather than an assumption. It writes
nothing to the database.

Usage:
    python3 measure_window.py --n 25 --window 40000
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
AAR = ROOT / "data" / "aar.db"
AAR_ROOT = ROOT.parent          # txt_file paths are relative to the repo root
LMSTUDIO = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "ornith-1.5-35b-a3b"


def _eo():
    spec = importlib.util.spec_from_file_location("eo", AAR_ROOT / "gst-aar" / "extract_ontology.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ask(prompt: str, content: str) -> dict | None:
    req = urllib.request.Request(
        LMSTUDIO,
        data=json.dumps({
            "model": MODEL,
            "temperature": 0,
            "max_tokens": 4000,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": content}],
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
        raw = resp["choices"][0]["message"]["content"] or ""
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"    parse failed: {type(e).__name__}", file=sys.stderr)
        return None


DECISION = re.compile(
    r"\b(?:we\s+rule|held\s+that|we\s+hold|in\s+view\s+of\s+the\s+(?:above|foregoing))\b",
    re.I)


def main(n: int, window: int, full: bool = False) -> None:
    eo = _eo()
    con = sqlite3.connect(AAR)
    con.row_factory = sqlite3.Row

    # The first version of this sampled the LARGEST rulings and used a 40,000-char
    # window — but the decision sits at ~75% of a ruling, so on a 150,000-char
    # document 40,000 chars still stopped well short of it. That measured nothing.
    # Sample instead on the property that matters: the decision is beyond the
    # production cap, and the document is small enough for the test window to
    # actually reach it.
    cap = window if not full else 10 ** 9
    sample = []
    for r in con.execute("""
            SELECT r.id, r.brief, r.txt_file, r.chars,
                   (SELECT COUNT(*) FROM ruling_questions q
                     WHERE q.ruling_id = r.id) AS qs,
                   (SELECT COUNT(*) FROM ruling_questions q
                     WHERE q.ruling_id = r.id
                       AND COALESCE(q.outcome_norm,'unknown') <> 'unknown') AS known
            FROM rulings r
            WHERE EXISTS (SELECT 1 FROM ruling_questions q WHERE q.ruling_id = r.id)
              AND NOT EXISTS (SELECT 1 FROM ruling_questions q
                              WHERE q.ruling_id = r.id
                                AND COALESCE(q.outcome_norm,'unknown') <> 'unknown')
            ORDER BY r.id"""):
        p = AAR_ROOT / "gst-aar" / r["txt_file"] if r["txt_file"] else None
        if not p or not p.exists():
            continue
        text = p.read_text(errors="replace")
        m = DECISION.search(text)
        if not m or m.start() <= 9000:
            continue                      # nothing was hidden by the cap
        if full and len(text) > 120_000:
            continue                      # keep the prompt within the model's window
        if not full and len(text) > cap:
            continue                      # the test window would not reach the decision
        sample.append((r, text))
        if len(sample) >= n:
            break

    if not sample:
        sys.exit("no rulings where the decision sits beyond the cap and the window reaches it")

    print(f"measuring {len(sample)} rulings whose decision is beyond the 9,000-char cap")
    print(f"window: {'FULL TEXT' if full else f'{window:,} chars'}\n")

    before_out = after_out = 0
    before_q = after_q = 0
    improved = []
    t0 = time.time()
    for i, (r, text) in enumerate(sample, 1):
        content = f"BRIEF: {(r['brief'] or '')[:1500]}\n\nTEXT (excerpt): {text[:window]}"
        d = ask(eo.LLM_Q_PROMPT, content)
        if not d:
            continue
        qs = [q for q in (d.get("questions") or [])
              if isinstance(q, dict) and q.get("question")]
        new_known = sum(1 for q in qs
                        if (q.get("outcome") or "").strip().lower()
                        not in ("", "null", "none"))
        before_q += r["qs"]
        after_q += len(qs)
        before_out += r["known"]
        after_out += new_known
        if new_known > r["known"]:
            improved.append((r["id"], r["qs"], len(qs), r["known"], new_known))
        print(f"  [{i}/{len(sample)}] ruling {r['id']} ({len(text):,} ch): "
              f"questions {r['qs']}->{len(qs)}, with outcome {r['known']}->{new_known}")

    print(f"\n=== result ({len(sample)} rulings, {(time.time()-t0)/60:.1f} min) ===")
    print(f"  questions found        {before_q:>4} -> {after_q:>4}")
    print(f"  questions with outcome {before_out:>4} -> {after_out:>4}")
    if improved:
        pct = round(100 * len(improved) / len(sample))
        print(f"\n  rulings that gained an outcome: {len(improved)} of {len(sample)}  ({pct}%)")
        for rid, bq, aq, bo, ao in improved[:10]:
            print(f"     ruling {rid}: {bo} -> {ao}")
    else:
        print("\n  no ruling gained an outcome — the window is NOT the cause")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--window", type=int, default=40000)
    ap.add_argument("--full", action="store_true",
                    help="send the whole text rather than a window")
    a = ap.parse_args()
    main(a.n, a.window, full=a.full)
