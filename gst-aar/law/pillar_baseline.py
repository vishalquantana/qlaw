#!/usr/bin/env python3
"""Baseline readiness for the three product pillars (see PRODUCT-PILLARS.md).

    python3 gst-aar/law/pillar_baseline.py

Reports how far the corpus is from supporting each pillar. The headline is the
"usable decision unit" — an issue, the provision that governs it, and how it was
decided. Everything in the pillars rests on it, and it is the binding constraint.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
AAR = ROOT / "data" / "aar.db"
LAW = ROOT / "data" / "law" / "law.db"

NN = "IS NOT NULL AND TRIM({c}) <> '' AND TRIM({c}) <> 'null'"
RULINGS = 2888


def pct(n: int, d: int) -> str:
    return f"{round(100 * n / max(d, 1)):>3}%"


def main() -> None:
    a = sqlite3.connect(AAR)
    one = lambda s: a.execute(s).fetchone()[0]  # noqa: E731

    print("=" * 66)
    print("PILLAR BASELINE")
    print("=" * 66)

    rulings = one("SELECT COUNT(*) FROM rulings")
    print(f"\nDECISION RECORD  (the foundation for all three pillars)")
    print(f"  rulings                              {rulings:>7,}")

    for label, table, col in (
            ("ruling has an outcome", "rulings", "outcome"),
            ("question has an outcome", "ruling_questions", "outcome_norm"),
            ("question has a held-summary", "ruling_questions", "held_summary"),
            ("subject has a rate", "ruling_subjects", "rate_proposed_norm")):
        tot = one(f"SELECT COUNT(*) FROM {table}")
        if col.endswith("_norm"):
            n = one(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL"
                    f" AND TRIM({col}) <> '' AND TRIM({col}) <> 'unknown'")
        else:
            n = one(f"SELECT COUNT(*) FROM {table} WHERE {col} " + NN.format(c=col))
        print(f"  {label:<36} {n:>6,}/{tot:<6,} {pct(n, tot)}")

    ruled = one("SELECT COUNT(DISTINCT ruling_id) FROM ruling_subjects"
                " WHERE rate_proposed_norm IS NOT NULL"
                " AND TRIM(rate_proposed_norm) <> ''")
    print(f"  {'rulings carrying a rate':<36} {ruled:>6,}/{rulings:<6,} {pct(ruled, rulings)}")

    kinds = [r[0] for r in a.execute("SELECT DISTINCT kind FROM ruling_citations")]
    planned = {"notification", "section", "rule", "circular", "schedule_entry", "precedent"}
    print(f"  citation kinds extracted             {len(kinds):>6,}/{len(planned):<6,} "
          f"{pct(len(kinds), len(planned))}   have={sorted(kinds)}")
    print(f"    missing: {sorted(planned - set(kinds))}")

    units = one("""SELECT COUNT(DISTINCT rq.ruling_id) FROM ruling_questions rq
                   WHERE rq.outcome_norm IS NOT NULL AND rq.outcome_norm <> 'unknown'
                     AND EXISTS (SELECT 1 FROM ruling_citations rc
                                 WHERE rc.ruling_id = rq.ruling_id)""")
    units_sec = one("""SELECT COUNT(DISTINCT rq.ruling_id) FROM ruling_questions rq
                       WHERE rq.outcome_norm IS NOT NULL AND rq.outcome_norm <> 'unknown'
                         AND EXISTS (SELECT 1 FROM ruling_citations rc
                                     WHERE rc.ruling_id = rq.ruling_id
                                       AND rc.kind = 'section')""")
    print(f"\n  DECISION RECORD (issue + provision + outcome)")
    print(f"    ... with ANY provision citation     {units:>6,}/{rulings:<6,} {pct(units, rulings)}")
    print(f"    ... with a SECTION citation         {units_sec:>6,}/{rulings:<6,} {pct(units_sec, rulings)}")

    # which side is the bottleneck: outcomes, or citations? A decision record needs
    # both, so the scarcer input is what limits the intersection.
    any_cit = one("SELECT COUNT(DISTINCT ruling_id) FROM ruling_citations")
    sec_cit = one("SELECT COUNT(DISTINCT ruling_id) FROM ruling_citations"
                  " WHERE kind = 'section'")
    any_out = one("SELECT COUNT(DISTINCT ruling_id) FROM ruling_questions"
                  " WHERE outcome_norm IS NOT NULL AND outcome_norm <> 'unknown'")
    print(f"\n  BOTTLENECK — a record needs both; the scarcer input limits it")
    print(f"    rulings with any citation           {any_cit:>6,}/{rulings:<6,} {pct(any_cit, rulings)}")
    print(f"    rulings with a section citation     {sec_cit:>6,}/{rulings:<6,} {pct(sec_cit, rulings)}")
    print(f"    rulings with an issue outcome       {any_out:>6,}/{rulings:<6,} {pct(any_out, rulings)}")
    print(f"    -> {'OUTCOMES' if any_out < any_cit else 'CITATIONS'} are the scarcer input")

    print(f"\nVOCABULARY CONSISTENCY")
    ks = [r[0] for r in a.execute(
        "SELECT DISTINCT kind FROM ruling_subjects WHERE kind IS NOT NULL")]
    have_norm = "kind_norm" in {r[1] for r in a.execute("PRAGMA table_info(ruling_subjects)")}
    print(f"  ruling_subjects.kind (as extracted)  {len(ks):>6,} values  {sorted(ks)}")
    if have_norm:
        nk = a.execute("SELECT kind_norm, COUNT(*) FROM ruling_subjects"
                       " GROUP BY kind_norm ORDER BY 2 DESC").fetchall()
        print(f"  ruling_subjects.kind_norm (clean)    {len(nk):>6,} values  "
              + ", ".join(f"{k}={v:,}" for k, v in nk))
    else:
        print("  -> run normalize_vocab.py to collapse these to 4 concepts")

    tags = a.execute("SELECT tag, COUNT(*) FROM ruling_tags GROUP BY tag"
                     " ORDER BY 2 DESC").fetchall()
    print(f"\n  sector tags                          {len(tags):>6,}   "
          f"top: {', '.join(f'{t} {n}' for t, n in tags[:5])}")

    print(f"\nPROVISIONS AVAILABLE TO CITE")
    l = sqlite3.connect(LAW)
    lone = lambda s: l.execute(s).fetchone()[0]  # noqa: E731
    tot = lone("SELECT COUNT(*) FROM documents WHERE kind='cbic_act_section'")
    wrd = lone("SELECT COUNT(*) FROM documents WHERE kind='cbic_act_section'"
               " AND body LIKE '%Text source: India Code%'")
    rules = lone("SELECT COUNT(*) FROM documents WHERE kind='cgst_rule'")
    codes = lone("SELECT COUNT(DISTINCT code) FROM rate_codes")
    print(f"  central Act sections worded          {wrd:>6,}/{tot:<6,} {pct(wrd, tot)}")
    print(f"  CGST Rules held                      {rules:>6,}")
    print(f"  HSN / SAC codes                      {codes:>6,}")

    print(f"\nMOST-CITED PROVISIONS (where the requirement model should start)")
    for ident, n in a.execute("""SELECT identifier, COUNT(*) FROM ruling_citations
                                 WHERE kind='section' GROUP BY identifier
                                 ORDER BY 2 DESC LIMIT 6"""):
        print(f"    {ident[:38]:40s} {n:>5}")
    l.close()
    a.close()

    print("\n" + "=" * 66)
    print("Phase 0 (vocabulary + decision record + citations + eval) gates all three.")
    print("=" * 66)


if __name__ == "__main__":
    main()
