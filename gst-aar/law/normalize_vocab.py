#!/usr/bin/env python3
"""Phase 0a — normalise the extracted vocabularies, and build the decision record.

Two problems this fixes, both of which block every product pillar:

1. **The extracted vocabularies are inconsistent.** `ruling_subjects.kind` holds
   seven spellings for four concepts (`good` / `goods`, `both` / `service|good`,
   `null` / `unspecified` / empty), and the two `outcome` columns use different
   words for the same idea (`answered` in `ruling_questions`, `ruling_given` in
   `rulings`). Aggregating over either is unreliable until this is fixed.

2. **There is no decision record.** The atomic unit every pillar needs — an issue,
   the provision that governs it, and how it was decided — exists only as three
   unjoined tables.

Nothing is overwritten: the normalised value goes in a new `*_norm` column so the
extracted original is preserved for audit, and the decision record is a view.

Usage: python3 normalize_vocab.py --check
       python3 normalize_vocab.py
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
AAR = HERE.parent / "data" / "aar.db"

# --- controlled vocabularies -------------------------------------------------

# what the applicant supplied
KIND_MAP = {
    "good": "good", "goods": "good",
    "service": "service",
    "both": "both", "service|good": "both",
    "unspecified": "unspecified", "null": "unspecified", "": "unspecified",
}

# one vocabulary shared by both outcome columns. `answered` (questions) and
# `ruling_given` (rulings) are the same fact, so they collapse to one term.
OUTCOME_MAP = {
    "ruling_given": "ruling_given", "answered": "ruling_given",
    "withdrawn": "withdrawn",
    "rejected": "rejected",
    "no_ruling": "no_ruling",
    "null": "unknown", "": "unknown",
}

DECISION_VIEW = """
DROP VIEW IF EXISTS decision_record;
CREATE VIEW decision_record AS
SELECT
    rq.ruling_id                                   AS ruling_id,
    r.id                                           AS case_id,
    r.applicant                                    AS applicant,
    r.state                                        AS state,
    r.category                                     AS application_category,
    COALESCE(r.outcome_norm, 'unknown')            AS ruling_outcome,
    rq.q_no                                        AS q_no,
    rq.question                                    AS issue,
    COALESCE(rq.outcome_norm, 'unknown')           AS issue_outcome,
    rq.held_summary                                AS held,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'section')       AS sections,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'rule')          AS rules,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'notification')  AS notifications,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'circular')      AS circulars,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'schedule_entry') AS schedule_entries,
    (SELECT GROUP_CONCAT(DISTINCT rc.identifier)
       FROM ruling_citations rc
      WHERE rc.ruling_id = rq.ruling_id AND rc.kind = 'precedent')     AS precedents,
    (SELECT GROUP_CONCAT(DISTINCT rs.hsn_sac)
       FROM ruling_subjects rs
      WHERE rs.ruling_id = rq.ruling_id AND rs.hsn_sac IS NOT NULL
        AND TRIM(rs.hsn_sac) <> '')                                    AS hsn_sac,
    (SELECT GROUP_CONCAT(DISTINCT rs.rate_proposed_norm)
       FROM ruling_subjects rs
      WHERE rs.ruling_id = rq.ruling_id AND rs.rate_proposed_norm IS NOT NULL
        AND TRIM(rs.rate_proposed_norm) <> '')                         AS rates_proposed,
    (SELECT rs.rate_held_norm FROM ruling_subjects rs
      WHERE rs.ruling_id = rq.ruling_id AND rs.rate_held_norm IS NOT NULL
        AND TRIM(rs.rate_held_norm) <> '' LIMIT 1)                     AS rate_held,
    (SELECT GROUP_CONCAT(DISTINCT rt.tag) FROM ruling_tags rt
      WHERE rt.ruling_id = rq.ruling_id)                               AS sectors,
    r.order_date                                   AS order_date,
    r.pdf_url                                      AS source_url
FROM ruling_questions rq
JOIN rulings r ON r.id = rq.ruling_id;
"""


def norm_rate_value(raw: str) -> str:
    """Canonicalise a rate so `18` and `18%` aggregate as one value.

    The two extraction passes wrote different formats — the regex pass stores the
    bare number, the LLM pass stores it with a percent sign — which would split any
    count by rate. Descriptive values ("Same rate of central tax as on supply of
    like goods") are left alone rather than forced into a number.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if s.lower() in ("nil", "nil.", "zero"):
        return "0%"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%?", s)
    if m:
        return f"{m.group(1)}%"
    return s


def normalise_rates(con: sqlite3.Connection) -> int:
    rows = con.execute(
        "SELECT id, COALESCE(rate_proposed,''), COALESCE(rate_held,'')"
        " FROM ruling_subjects").fetchall()
    n = 0
    for rid, prop, held in rows:
        con.execute("UPDATE ruling_subjects SET rate_proposed_norm=?, rate_held_norm=?"
                    " WHERE id=?", (norm_rate_value(prop), norm_rate_value(held), rid))
        n += 1
    con.commit()
    return n


def add_columns(con: sqlite3.Connection) -> None:
    for table, col in (("ruling_subjects", "kind_norm"),
                       ("ruling_subjects", "rate_proposed_norm"),
                       ("ruling_subjects", "rate_held_norm"),
                       ("ruling_questions", "outcome_norm"),
                       ("rulings", "outcome_norm")):
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if col not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    con.commit()


def normalise(con: sqlite3.Connection, mapping: dict, table: str,
              src: str, dst: str) -> int:
    rows = con.execute(
        f"SELECT DISTINCT COALESCE({src}, '') FROM {table}").fetchall()
    changed = 0
    for (raw,) in rows:
        key = (raw or "").strip().lower()
        # anything unmapped becomes the honest fallback rather than passing through
        out = mapping.get(key, "unknown" if dst.endswith("outcome_norm")
                          else "unspecified")
        cur = con.execute(
            f"UPDATE {table} SET {dst} = ? WHERE COALESCE({src}, '') = ?",
            (out, raw))
        changed += cur.rowcount
    con.commit()
    return changed


def main(check: bool = False, view_only: bool = False) -> None:
    con = sqlite3.connect(AAR)

    if view_only:
        # the view is derived; only the columns it reads must exist
        add_columns(con)
        con.executescript(DECISION_VIEW)
        con.commit()
        print("decision_record view rebuilt")
    else:
        print("=== vocabulary drift, before ===")
        for table, col in (("ruling_subjects", "kind"),
                           ("ruling_questions", "outcome"),
                           ("rulings", "outcome")):
            vals = [r[0] for r in con.execute(
                f"SELECT DISTINCT COALESCE({col}, '(null)') FROM {table}")]
            print(f"  {table}.{col}: {len(vals)} values -> {sorted(str(v) for v in vals)}")

        if check:
            print("\n(dry run)")
            con.close()
            return

        add_columns(con)
        n1 = normalise(con, KIND_MAP, "ruling_subjects", "kind", "kind_norm")
        n2 = normalise(con, OUTCOME_MAP, "ruling_questions", "outcome", "outcome_norm")
        n3 = normalise(con, OUTCOME_MAP, "rulings", "outcome", "outcome_norm")
        n4 = normalise_rates(con)
        print(f"\nrows normalised: subjects {n1:,}  questions {n2:,}  "
              f"rulings {n3:,}  rates {n4:,}")

        con.executescript(DECISION_VIEW)
        con.commit()

        print("\n=== after ===")
        for table, col in (("ruling_subjects", "kind_norm"),
                           ("ruling_questions", "outcome_norm"),
                           ("rulings", "outcome_norm")):
            dist = con.execute(
                f"SELECT {col}, COUNT(*) FROM {table} GROUP BY {col} ORDER BY 2 DESC"
            ).fetchall()
            print(f"  {table}.{col}: " + ", ".join(f"{k}={v:,}" for k, v in dist))
        rates = con.execute(
            "SELECT rate_proposed_norm, COUNT(*) FROM ruling_subjects"
            " WHERE rate_proposed_norm IS NOT NULL AND TRIM(rate_proposed_norm)<>''"
            " GROUP BY rate_proposed_norm ORDER BY 2 DESC LIMIT 8").fetchall()
        print("  rate_proposed_norm: " + ", ".join(f"{k}={v:,}" for k, v in rates))

    total = con.execute("SELECT COUNT(*) FROM decision_record").fetchone()[0]
    usable = con.execute(
        "SELECT COUNT(*) FROM decision_record"
        " WHERE issue_outcome <> 'unknown' AND sections IS NOT NULL").fetchone()[0]
    print(f"\n=== decision_record view ===")
    print(f"  rows                              {total:,}")
    print(f"  issue + provision + outcome       {usable:,}  "
          f"({round(100 * usable / max(total, 1))}%)")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--view-only", action="store_true",
                    help="rebuild just the decision_record view")
    args = ap.parse_args()
    main(check=args.check, view_only=args.view_only)
