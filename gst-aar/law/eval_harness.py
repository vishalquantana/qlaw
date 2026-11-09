#!/usr/bin/env python3
"""Evaluation harness — the gate on all three pillars.

Nothing in this project should be put in front of an assessing officer without an
accuracy figure, and an accuracy figure needs something to measure against. This
provides three things:

  --check              automated integrity checks, runnable today
  --sample N           a stratified sample drawn for expert labelling
  --score labels.csv   precision against the returned labels

**What --check can and cannot tell us.** It measures whether what we extracted is
*internally consistent and resolvable* — that a cited section actually exists in the
corpus, that an extracted HSN code appears in the rate schedule. That is a real and
useful signal: an unresolvable citation is either an extraction error or a hole in
the corpus, and both are worth knowing.

It cannot tell us whether an extraction is *legally correct*. Only an expert can.
That is what the labelling sheet is for, and the harness deliberately does not
pretend otherwise.

Usage:
    python3 eval_harness.py --check
    python3 eval_harness.py --sample 150
    python3 eval_harness.py --score eval/labels.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
AAR = ROOT / "data" / "aar.db"
LAW = ROOT / "data" / "law" / "law.db"
EVAL_DIR = ROOT / "data" / "law" / "eval"

SECTION_ID = re.compile(r"^(CGST|SGST|IGST|UTGST)\s+s\.(.+)$", re.I)

# Which Act each citation prefix refers to. Section numbers COLLIDE across Acts —
# 161 of 174 numbers are claimed by more than one Act, so a lookup on the number
# alone silently matches the wrong statute (Customs s.98 instead of CGST s.98).
ACT_FOR_PREFIX = {
    "CGST": "Central Goods and Services Tax Act, 2017",
    "IGST": "Integrated Goods And Services Tax Act, 2017",
    "UTGST": "Union Territory Goods And Services Tax Act, 2017",
}
# State GST Acts are not held as sections. They mirror the CGST Act by design, but
# treating that as equivalence is a legal claim this check should not make silently,
# so SGST citations are counted and reported separately.
STATE_PREFIXES = {"SGST"}


def base_section(rest: str) -> str:
    """'98(4)' -> '98'; '2(30)' -> '2'; '11A(2)' -> '11A'."""
    m = re.match(r"(\d{1,3}[A-Z]?)", (rest or "").strip(), re.I)
    return m.group(1).upper() if m else ""


# --------------------------------------------------------------------------- #
# automated integrity checks
# --------------------------------------------------------------------------- #

def check_citation_resolvability(aar: sqlite3.Connection, law: sqlite3.Connection) -> dict:
    """Does a cited section exist in the corpus, **for the Act it names**?

    Keying on the section number alone is wrong and produces a misleadingly high
    figure: 161 of 174 section numbers are shared between Acts, so "s.98" matches
    the Customs Act's section 98 as readily as the CGST Act's. The lookup is
    therefore (Act, number), and SGST citations are reported separately because the
    State Acts are not held as sections.
    """
    have: set[tuple[str, str]] = set()
    for num, body in law.execute(
            "SELECT number, body FROM documents WHERE kind='cbic_act_section'"):
        m = re.search(r"^Act:\s*(.+)$", body or "", re.M)
        if not m:
            continue
        n = re.sub(r"^Section\s*", "", (num or "").strip(), flags=re.I).upper()
        have.add((m.group(1).strip().lower(), n))

    stats = {"central_total": 0, "central_resolved": 0, "state_total": 0}
    unresolved: Counter = Counter()
    for (ident,) in aar.execute("SELECT identifier FROM ruling_citations WHERE kind='section'"):
        m = SECTION_ID.match((ident or "").strip())
        if not m:
            continue
        prefix, num = m.group(1).upper(), base_section(m.group(2))
        if not num:
            continue
        if prefix in STATE_PREFIXES:
            stats["state_total"] += 1
            continue
        act = ACT_FOR_PREFIX.get(prefix)
        if not act:
            continue
        stats["central_total"] += 1
        if (act.lower(), num) in have:
            stats["central_resolved"] += 1
        else:
            unresolved[f"{prefix} s.{num}"] += 1
    stats["unresolved"] = unresolved
    return stats


def check_hsn_in_schedule(aar: sqlite3.Connection, law: sqlite3.Connection) -> dict:
    """Does an extracted HSN / SAC code appear anywhere in the rate schedule?"""
    codes = {r[0] for r in law.execute("SELECT DISTINCT code FROM rate_codes")}
    total = matched = 0
    unmatched: Counter = Counter()
    for (raw,) in aar.execute(
            "SELECT hsn_sac FROM ruling_subjects"
            " WHERE hsn_sac IS NOT NULL AND TRIM(hsn_sac)<>''"):
        for c in re.findall(r"\d{4,8}", raw or ""):
            total += 1
            # a 4-digit heading matches the schedule's 4-digit entry
            if c in codes or c[:4] in codes:
                matched += 1
            else:
                unmatched[c] += 1
    return {"total": total, "matched": matched, "unmatched": unmatched}


def check_rate_slab_validity(aar: sqlite3.Connection, law: sqlite3.Connection) -> dict:
    """Is every recorded rate a real slab in the schedule?"""
    slabs = set()
    for col in ("cgst_rate", "igst_rate"):
        for (v,) in law.execute(f"SELECT DISTINCT {col} FROM rate_facts"):
            m = re.match(r"(\d+(?:\.\d+)?)\s*%", (v or "").strip())
            if m:
                slabs.add(float(m.group(1)))
            elif (v or "").strip().lower() == "nil":
                slabs.add(0.0)
    total = valid = 0
    bad: Counter = Counter()
    for (v,) in aar.execute(
            "SELECT rate_proposed_norm FROM ruling_subjects"
            " WHERE rate_proposed_norm IS NOT NULL AND TRIM(rate_proposed_norm)<>''"):
        m = re.fullmatch(r"(\d+(?:\.\d+)?)%", (v or "").strip())
        if not m:
            continue                       # descriptive value, not a number
        total += 1
        if float(m.group(1)) in slabs:
            valid += 1
        else:
            bad[v] += 1
    return {"total": total, "valid": valid, "invalid": bad}


def check_cross_pass_agreement(aar: sqlite3.Connection) -> dict:
    """Where two passes both recorded a rate for the same ruling, do they agree?

    Disagreement is a genuine signal — one of the two is wrong — and it needs no
    expert to surface.
    """
    rows = aar.execute("""
        SELECT ruling_id,
               GROUP_CONCAT(DISTINCT rate_proposed_norm) AS vals
        FROM ruling_subjects
        WHERE rate_proposed_norm IS NOT NULL AND TRIM(rate_proposed_norm) <> ''
        GROUP BY ruling_id HAVING COUNT(DISTINCT rate_proposed_norm) > 1""").fetchall()
    total = aar.execute("""
        SELECT COUNT(*) FROM (SELECT ruling_id FROM ruling_subjects
          WHERE rate_proposed_norm IS NOT NULL AND TRIM(rate_proposed_norm) <> ''
          GROUP BY ruling_id)""").fetchone()[0]
    return {"rulings_with_rate": total, "conflicting": rows}


def run_checks() -> None:
    aar = sqlite3.connect(AAR)
    law = sqlite3.connect(LAW)

    print("=" * 68)
    print("AUTOMATED INTEGRITY CHECKS")
    print("=" * 68)
    print("\nThese measure internal consistency and resolvability. They cannot")
    print("measure legal correctness — only an expert can, via the label sheet.\n")

    c = check_citation_resolvability(aar, law)
    pct = round(100 * c["central_resolved"] / max(c["central_total"], 1))
    print(f"CITATION RESOLVABILITY  (resolved per Act — numbers collide between Acts)")
    print(f"  central-Act citations            {c['central_total']:>7,}")
    print(f"  ... resolve to a held section    {c['central_resolved']:>7,}   {pct}%")
    if c["unresolved"]:
        print(f"  top unresolved:")
        for ident, n in c["unresolved"].most_common(8):
            print(f"     {ident[:40]:42s} {n:>4}")
    print(f"  state-Act citations (SGST)       {c['state_total']:>7,}   "
          f"not held as sections — reported separately, not counted as failures")

    h = check_hsn_in_schedule(aar, law)
    pct = round(100 * h["matched"] / max(h["total"], 1))
    print(f"\nHSN / SAC RESOLVABILITY")
    print(f"  codes extracted from rulings     {h['total']:>7,}")
    print(f"  ... found in the rate schedule   {h['matched']:>7,}   {pct}%")
    if h["unmatched"]:
        print(f"  top not in schedule: "
              f"{', '.join(f'{k}({v})' for k, v in h['unmatched'].most_common(6))}")

    r = check_rate_slab_validity(aar, law)
    pct = round(100 * r["valid"] / max(r["total"], 1))
    print(f"\nRATE SLAB VALIDITY")
    print(f"  numeric rates recorded           {r['total']:>7,}")
    print(f"  ... on a real GST slab           {r['valid']:>7,}   {pct}%")
    if r["invalid"]:
        print(f"  off-slab: {', '.join(f'{k}({v})' for k, v in r['invalid'].most_common(6))}")

    a = check_cross_pass_agreement(aar)
    print(f"\nCROSS-PASS RATE AGREEMENT")
    print(f"  rulings carrying a rate          {a['rulings_with_rate']:>7,}")
    print(f"  ... with conflicting values      {len(a['conflicting']):>7,}   "
          f"{round(100 * len(a['conflicting']) / max(a['rulings_with_rate'], 1))}%")
    for rid, vals in a["conflicting"][:5]:
        print(f"     ruling {rid}: {vals}")

    print("\n" + "=" * 68)
    aar.close()
    law.close()


# --------------------------------------------------------------------------- #
# sampling for expert labelling
# --------------------------------------------------------------------------- #

LABEL_COLUMNS = ["ruling_id", "q_no", "state", "sector", "issue",
                 "provisions_we_found", "outcome_we_recorded", "rate_we_recorded",
                 "issue_ok", "provisions_ok", "outcome_ok", "rate_ok", "notes"]


def make_sample(n: int, seed: int = 7) -> Path:
    """Stratified by sector so the sample is not dominated by manufacturing."""
    aar = sqlite3.connect(AAR)
    rows = aar.execute("""
        SELECT dr.ruling_id, dr.q_no, dr.state, dr.sectors, dr.issue,
               dr.sections, dr.issue_outcome, dr.rates_proposed
        FROM decision_record dr
        WHERE dr.issue IS NOT NULL AND TRIM(dr.issue) <> ''
          AND dr.issue_outcome <> 'unknown'
          AND dr.sections IS NOT NULL""").fetchall()
    if not rows:
        aar.close()
        raise SystemExit("no scored rows available — run the questions pass first")

    by_sector: dict[str, list] = defaultdict(list)
    for r in rows:
        key = (r[3] or "unspecified").split(",")[0].strip() or "unspecified"
        by_sector[key].append(r)

    rng = random.Random(seed)
    per = max(1, n // max(len(by_sector), 1))
    picked = []
    for key, items in sorted(by_sector.items()):
        picked.extend(rng.sample(items, min(per, len(items))))
    picked = picked[:n]

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_DIR / "labels.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(LABEL_COLUMNS)
        for rid, qno, state, sector, issue, sections, outcome, rates in picked:
            w.writerow([rid, qno, state, sector, (issue or "")[:220], sections,
                        outcome, rates, "", "", "", "", ""])
    aar.close()
    print(f"wrote {len(picked)} rows across {len(by_sector)} sectors -> {out}")
    print("\nThe last five columns are for the reviewer: put 1 (correct),")
    print("0 (incorrect) or ? (unsure) in issue_ok / provisions_ok / outcome_ok /")
    print("rate_ok. Then run:  python3 eval_harness.py --score " + str(out))
    return out


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def score(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"no label file at {path}")
    rows = list(csv.DictReader(path.open()))
    fields = ["issue_ok", "provisions_ok", "outcome_ok", "rate_ok"]

    print("=" * 68)
    print(f"SCORING — {path.name}")
    print("=" * 68)
    print(f"\n  labelled rows: {len(rows)}\n")
    if not rows:
        return

    print(f"  {'field':<16} {'scored':>7} {'correct':>8} {'wrong':>7} {'unsure':>7} {'precision':>10}")
    for f in fields:
        scored = [r[f].strip() for r in rows if r.get(f, "").strip() in ("0", "1")]
        correct = sum(1 for v in scored if v == "1")
        wrong = sum(1 for v in scored if v == "0")
        unsure = sum(1 for r in rows if r.get(f, "").strip() == "?")
        p = f"{round(100 * correct / len(scored))}%" if scored else "n/a"
        print(f"  {f:<16} {len(scored):>7} {correct:>8} {wrong:>7} {unsure:>7} {p:>10}")

    print("\n  A figure here covers only the sampled rows. Quote it with the sample")
    print("  size and the date, never as a general accuracy claim.")
    print("=" * 68)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N")
    ap.add_argument("--score", metavar="LABELS_CSV")
    args = ap.parse_args()
    if args.check:
        run_checks()
    elif args.sample:
        make_sample(args.sample)
    elif args.score:
        score(Path(args.score))
    else:
        ap.error("choose --check, --sample N or --score FILE")


if __name__ == "__main__":
    main()
