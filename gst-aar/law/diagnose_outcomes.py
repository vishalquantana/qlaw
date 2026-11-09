#!/usr/bin/env python3
"""Why does the outcome gap exist? Separate "the order is silent" from "we missed it".

The truncation hypothesis was tested and rejected (see measure_window.py). That leaves
three candidates for the ~4,400 question rows with no outcome:

  (a) the order genuinely does not state an outcome — a disposal or withdrawal order
  (b) the order states one, but the prompt does not elicit it
  (c) the order states one and the model failed to extract it

(a) is not a defect. (b) and (c) are, and they need different fixes. This separates
them using the full text and no LLM calls at all: if the text contains the kind of
sentence a ruling uses to decide something, the outcome was there to be found.

Usage: python3 diagnose_outcomes.py --n 200
"""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
AAR = ROOT / "data" / "aar.db"
REPO = ROOT.parent          # txt_file paths are relative to the repo root

# Phrases a ruling uses when it actually decides something. Deliberately broad — the
# point is to detect that a decision sentence exists, not to parse it.
DECISION_MARKERS = [
    (r"\bwe\s+hold\b", "we hold"),
    (r"\bheld\s+that\b", "held that"),
    (r"\bwe\s+are\s+of\s+the\s+(?:considered\s+)?opinion\b", "we are of the opinion"),
    (r"\banswered\s+in\s+the\s+(?:affirmative|negative)\b", "answered in the ..."),
    (r"\bthe\s+question\s+is\s+answered\b", "the question is answered"),
    (r"\bruling\s+is\s+(?:given|pronounced|passed)\b", "ruling is given"),
    (r"\baccordingly,?\s+we\s+(?:rule|hold)\b", "accordingly we rule"),
    (r"\bwe\s+rule\b", "we rule"),
    (r"\bit\s+is\s+(?:hereby\s+)?(?:ruled|held)\b", "it is ruled"),
    (r"\bthe\s+rate\s+of\s+(?:tax|gst|integrated\s+tax|central\s+tax)\b.{0,60}?\bis\b",
     "the rate of tax ... is"),
    (r"\b(?:application|appeal)\s+is\s+(?:hereby\s+)?(?:rejected|allowed|dismissed)\b",
     "application is rejected/allowed"),
    (r"\bin\s+view\s+of\s+the\s+(?:above|foregoing|discussion)\b", "in view of the above"),
    (r"\bwe\s+accordingly\b", "we accordingly"),
]
COMPILED = [(re.compile(p, re.I), label) for p, label in DECISION_MARKERS]

# A withdrawal or a rejection on maintainability is a disposition, not a decision on
# the substantive question — (a), not (b)/(c).
DISPOSAL_ONLY = re.compile(
    r"withdrawn|infructuous|not\s+maintainable|outside\s+the\s+(?:purview|mandate)"
    r"|non-?prosecution|no\s+manual\s+copy", re.I)


def main(n: int) -> None:
    con = sqlite3.connect(AAR)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT r.id, r.txt_file, r.chars, r.brief
        FROM rulings r
        WHERE EXISTS (SELECT 1 FROM ruling_questions q WHERE q.ruling_id = r.id
                        AND COALESCE(q.outcome_norm,'unknown') = 'unknown')
        ORDER BY r.id LIMIT ?""", (n,)).fetchall()

    silent = missed = disposal = notext = 0
    missed_examples = []
    marker_counts = collections.Counter()

    for r in rows:
        p = REPO / "gst-aar" / r["txt_file"] if r["txt_file"] else None
        if not p or not p.exists():
            notext += 1
            continue
        text = p.read_text(errors="replace")
        found = [(rx, lab) for rx, lab in COMPILED if rx.search(text)]
        if not found:
            silent += 1
            continue
        for _, lab in found:
            marker_counts[lab] += 1
        if DISPOSAL_ONLY.search(r["brief"] or "") and len(found) <= 1:
            # a withdrawal/disposal order; a stray "in view of the above" is not a
            # decision on a substantive question
            disposal += 1
            continue
        missed += 1
        if len(missed_examples) < 6:
            hit = found[0]
            m = hit[0].search(text)
            missed_examples.append((r["id"], hit[1],
                                   text[max(0, m.start() - 90):m.end() + 140]
                                   .replace("\n", " ")[:230]))

    total = len(rows)
    print(f"sampled {total} rulings with an unknown outcome\n")
    print(f"  (a) order genuinely silent        {silent:>4}  {round(100*silent/max(total,1)):>3}%")
    print(f"      withdrawal / disposal only    {disposal:>4}  {round(100*disposal/max(total,1)):>3}%")
    print(f"  (b/c) a decision sentence EXISTS  {missed:>4}  {round(100*missed/max(total,1)):>3}%")
    if notext:
        print(f"      no text file                  {notext:>4}")
    print()
    print("  (a) is not a defect — those orders decide nothing to record.")
    print("  (b/c) is the real loss: the decision was in the text and we did not get it.")
    print()
    print("  decision markers seen:")
    for lab, c in marker_counts.most_common(10):
        print(f"     {c:>4}  {lab}")
    if missed_examples:
        print("\n  examples of decisions that were present but not extracted:")
        for rid, lab, snippet in missed_examples:
            print(f"\n     ruling {rid}  [{lab}]")
            print(f"       ...{snippet}...")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    main(ap.parse_args().n)
