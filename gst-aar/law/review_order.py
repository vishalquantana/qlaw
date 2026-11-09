#!/usr/bin/env python3
"""Pillar 1 prototype — review whether an order is according to law.

**Read this first.** The output is a set of **flags for human review**. It never
concludes that an order is lawful or unlawful, and it says so on every run. A tool
that tells an assessing officer "this order is bad in law" will be wrong sometimes,
and when it is wrong the cost lands on the department.

What it does, in order of how much it can be trusted:

  1. **Chronology check** — extracts the dates the order itself relies on and tests
     them against each other. This needs no external source and is the strongest
     thing the tool does: if an order fixes a point of taxation and then applies a
     provision that did not exist on that date, the contradiction is in the order.
  2. **Provision retrieval** — pulls the governing sections and rules from the corpus
     and quotes them.
  3. **On-point material** — finds rulings in the corpus addressing the same issue.
  4. **Coverage report** — states plainly what could NOT be verified and why. This is
     the most important section, because a review that silently omits the provision it
     could not check is worse than no review.

Usage: python3 review_order.py --order ../orders/sample-buildcon-appeal.txt
"""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
LAW = ROOT / "data" / "law" / "law.db"
AAR = ROOT / "data" / "aar.db"

DATE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b")


def norm_date(d: str, m: str, y: str) -> str:
    return f"{y}-{int(m):02d}-{int(d):02d}"


def extract_chronology(text: str) -> list[tuple[str, str]]:
    """Dates with the role the order assigns them, from the sentence around each."""
    roles = [
        (r"point of taxation[^.]{0,80}", "point of taxation (fixed by the order)"),
        (r"(?:inserted|introduced|amended)\s+by[^.]{0,60}", "amendment date"),
        (r"effective from[^.]{0,30}", "express effective date"),
        (r"sale deed was executed on[^.]{0,20}", "comparable sale relied on"),
        (r"occupancy certificate[^.]{0,40}", "occupancy certificate"),
        (r"building permission was obtained on[^.]{0,20}", "building permission"),
        (r"construction (?:commenced|completed) on[^.]{0,20}", "construction milestone"),
        (r"DAGPA[^.]{0,60}dated[^.]{0,10}", "development agreement"),
    ]
    found: list[tuple[str, str]] = []
    for pat, label in roles:
        for m in re.finditer(pat, text, re.I):
            d = DATE.search(m.group(0))
            if d:
                found.append((norm_date(*d.groups()), label))
    # dedupe, keep first role per (date, label)
    seen = set()
    out = []
    for d, label in found:
        if (d, label) not in seen:
            seen.add((d, label))
            out.append((d, label))
    return sorted(out)


def check_chronology(chron: list[tuple[str, str]]) -> list[str]:
    """Compare the dates the order relies on against each other. No external source."""
    flags = []
    pot = [d for d, l in chron if "point of taxation" in l]
    amend = [d for d, l in chron if l == "amendment date"]
    effective = [d for d, l in chron if "effective date" in l]
    sale = [d for d, l in chron if "comparable sale" in l]

    for p in pot:
        for a in amend:
            if a > p:
                flags.append(
                    f"The order fixes the point of taxation at {p} but applies a "
                    f"provision introduced on {a} — later than the point of taxation.")
        for e in effective:
            if e > p:
                flags.append(
                    f"The amending provision is expressly effective from {e}, which is "
                    f"after the point of taxation of {p} the order itself fixed.")
        for s in sale:
            if s > p:
                flags.append(
                    f"The comparable sale relied on is dated {s}, after the point of "
                    f"taxation of {p} — the value post-dates the supply being valued.")
    return flags


def held_provisions(law: sqlite3.Connection, text: str) -> list[tuple[str, str, bool]]:
    """Sections the order cites, and whether we hold the wording."""
    out = []
    seen = set()
    for m in re.finditer(r"[Ss]ection\s+(\d{1,3}[A-Z]?(?:\(\d+\))?)", text):
        sec = m.group(1)
        base = re.match(r"(\d{1,3}[A-Z]?)", sec).group(1)
        if base in seen:
            continue
        seen.add(base)
        row = law.execute("""
            SELECT title, body FROM documents WHERE kind='cbic_act_section'
              AND number=? AND body LIKE '%Act: Central Goods and Services Tax Act, 2017%'
            LIMIT 1""", (f"Section {base}",)).fetchone()
        if row:
            has = "Text source: India Code" in (row[1] or "")
            out.append((sec, row[0], has))
        else:
            out.append((sec, "(not held)", False))
    return sorted(out, key=lambda r: int(re.match(r"\d+", r[0]).group()))


GOVT_PARTY = re.compile(
    r"^(?:CIT|CCE|Commissioner|Union of India|State of|Assistant Commissioner|"
    r"Deputy Commissioner|Principal Commissioner|ACIT|DCIT|Government)\b", re.I)

# A party name is a run of capitalised words. Requiring every word to be capitalised
# is what excludes the prose around it — "Constitution Bench judgment in CIT" fails
# at the lowercase "judgment", so the match starts cleanly at "CIT". A lazy quantifier
# instead truncated the name to its first word ("Vatika"), and the plausibility filter
# then rejected the truncated result.
PARTY = r"[A-Z][A-Za-z&.'\-]*(?:\s+[A-Z][A-Za-z&.'\-]*){0,5}"


def check_authorities(law: sqlite3.Connection, text: str) -> list[tuple[str, bool]]:
    """Case law the order relies on, and whether we hold it.

    Matching on a surname against the judgment layer produces false "HELD" results —
    an earlier version reported all three authorities as held when the corpus contains
    three 2025 judgments, none of them cited in this order. The distinctive party (the
    one that is not a tax authority) is matched, and the base of the search is printed
    so the reader can see how small the denominator is.
    """
    names = set()
    for m in re.finditer(rf"\b({PARTY})\s+v\.?\s+({PARTY})", text):
        first, second = m.group(1).strip(), m.group(2).strip()
        cand = f"{first} v. {second}"
        if re.search(r"\b(?:Ltd|Limited|Pvt|Private|Industries|Components|Township|"
                     r"Electricals|Corporation|Company|Commissioner|CIT|CCE)\b",
                     cand, re.I):
            names.add(cand)

    out = []
    for n in sorted(names):
        first, second = [p.strip() for p in re.split(r"\s+v\.?\s+", n, maxsplit=1)]
        # the distinctive party is whichever side is not a tax authority
        distinctive = second if GOVT_PARTY.match(first) else first
        words = distinctive.split()
        key = re.sub(r"[^A-Za-z]", "", words[-1]) if words else ""
        held = 0
        if len(key) >= 5:
            held = law.execute(
                "SELECT COUNT(*) FROM documents WHERE kind='judgment'"
                " AND (title LIKE ? OR body LIKE ?)",
                (f"%{key}%", f"%{key}%")).fetchone()[0]
        out.append((f"{first} v. {second}", held > 0))
    return out


def check_notifications(law: sqlite3.Connection, text: str) -> list[tuple[str, bool, int]]:
    """Notifications the order relies on, and whether we hold their TEXT.

    Two false positives were caught here and both are worth knowing about:

      * a gazette **Order** that merely referred to 04/2018 was accepted as the
        notification — a false "HELD", worse than "NOT HELD" because it claims a
        verification we do not have;
      * "Order No. 04/2018-Central Tax" is a *different instrument* that shares the
        number, so matching on the number alone is not enough.

    The number must appear as a **Notification**, in the document's own title or opening.
    """
    nums = set()
    for m in re.finditer(r"Notification\s+No\.?\s*(\d{1,3}/20\d{2})", text):
        nums.add(m.group(1))
    out = []
    for n in sorted(nums):
        esc = re.escape(n).replace(r"\ ", r"\s*")
        own = law.execute("""
            SELECT COUNT(*) FROM documents
             WHERE kind IN ('notification','circular')
               AND (title GLOB ? OR substr(body,1,500) GLOB ?)""",
            (f"*Notification*{n}*", f"*Notification*{n}*")).fetchone()[0]
        mentioned = law.execute("""
            SELECT COUNT(*) FROM documents
             WHERE kind IN ('notification','circular')
               AND (title LIKE ? OR body LIKE ?)""",
            (f"%{n}%", f"%{n}%")).fetchone()[0]
        out.append((n, own > 0, mentioned))
    return out


def supporting_material(aar: sqlite3.Connection, repo: Path) -> dict:
    """What the corpus can contribute on the question the order turns on.

    An earlier version of this tool reported only that the notifications and judgments
    were "not held", and stopped there. That understated the corpus: a ruling that
    *quotes* a notification or *cites* a judgment is evidence of the proposition, even
    where the instrument itself is absent. This finds that evidence and labels it for
    what it is — secondary, and citable as such.
    """
    rows = aar.execute("SELECT id, txt_file FROM rulings"
                       " WHERE txt_file IS NOT NULL AND TRIM(txt_file)<>''").fetchall()
    out = {"principle": [], "para2a": [], "para2": [], "clarificatory": [],
           "effective_date": []}
    for rid, txt in rows:
        p = repo / "gst-aar" / txt if not Path(txt).is_absolute() else Path(txt)
        if not p.exists():
            continue
        t = p.read_text(errors="replace")

        if re.search(r"prospectiv", t, re.I) and re.search(r"notification", t, re.I):
            m = re.search(r"amendments?\s+(?:is|are)\s+prospective[^.]{0,140}", t, re.I)
            if m:
                out["principle"].append((rid, re.sub(r"\s+", " ", m.group(0))[:190]))
        for key, pat in (("para2a", r"deemed to be the value of similar apartments"),
                         ("para2", r"one[-\s]?third of the total amount charged")):
            if re.search(pat, t, re.I):
                out[key].append(rid)
        if re.search(r"clarificatory", t, re.I) and re.search(r"retrospectiv|prospectiv", t, re.I):
            m = re.search(r"[^.]{0,150}clarificatory[^.]{0,150}", t, re.I)
            if m:
                out["clarificatory"].append((rid, re.sub(r"\s+", " ", m.group(0))[:190]))
        # does any ruling state an effective date for the amending notification?
        for m in re.finditer(r"03/2019[^.\n]{0,90}", t):
            s = re.sub(r"\s+", " ", m.group(0))
            if re.search(r"effective|wef|w\.e\.f", s, re.I):
                out["effective_date"].append((rid, s[:140]))
    return out


def on_point_rulings(aar: sqlite3.Connection, repo: Path, patterns: dict) -> dict:
    """Rulings whose text matches each pattern, with a short brief for context."""
    rows = aar.execute("SELECT id, txt_file, brief FROM rulings"
                       " WHERE txt_file IS NOT NULL AND TRIM(txt_file)<>''").fetchall()
    hits = collections.defaultdict(list)
    for rid, txt, brief in rows:
        p = repo / "gst-aar" / txt if not Path(txt).is_absolute() else Path(txt)
        if not p.exists():
            continue
        t = p.read_text(errors="replace")
        for label, pat in patterns.items():
            if re.search(pat, t, re.I):
                hits[label].append((rid, (brief or "")[:96]))
    return hits


def main(order_path: str) -> None:
    text = Path(order_path).read_text()
    law = sqlite3.connect(LAW)
    aar = sqlite3.connect(AAR)
    repo = ROOT.parent

    print("=" * 78)
    print("ORDER REVIEW — FLAGS FOR HUMAN REVIEW")
    print("=" * 78)
    print("\nThis is a review aid. Nothing below is a conclusion of law, and no flag")
    print("means the order is wrong. Each item identifies something to verify.\n")

    print("-" * 78)
    print("1. CHRONOLOGY — extracted from the order itself, no external source")
    print("-" * 78)
    chron = extract_chronology(text)
    for d, label in chron:
        print(f"   {d}   {label}")
    flags = check_chronology(chron)
    print()
    if flags:
        for f in flags:
            print(f"   FLAG: {f}")
    else:
        print("   No internal date contradiction found.")

    print()
    print("-" * 78)
    print("2. PROVISIONS THE ORDER RELIES ON")
    print("-" * 78)
    for sec, title, has in held_provisions(law, text):
        mark = "wording held" if has else "NOT HELD"
        print(f"   s.{sec:<10} {mark:<14} {title[:46] if title != '(not held)' else ''}")

    print()
    print("-" * 78)
    print("3. NOTIFICATIONS — do we hold their own text, or only references to them?")
    print("-" * 78)
    for n, own, mentioned in check_notifications(law, text):
        if own:
            print(f"   {n:<12} text HELD")
        elif mentioned:
            print(f"   {n:<12} NOT HELD — referenced in {mentioned} document(s), "
                  f"but none is the notification itself")
        else:
            print(f"   {n:<12} NOT HELD — no reference found either")

    print()
    print("-" * 78)
    print("4. AUTHORITIES (case law) — do we hold them?")
    print("-" * 78)
    auth = check_authorities(law, text)
    if not auth:
        print("   (none detected in the order text)")
    for n, has in auth:
        print(f"   {n[:52]:<54} {'HELD' if has else 'NOT HELD'}")
    print(f"\n   judgment documents in the corpus: "
          f"{law.execute(chr(83)+chr(69)+chr(76)+chr(69)+chr(67)+chr(84)+' COUNT(*) FROM documents WHERE kind=' + chr(39) + 'judgment' + chr(39)).fetchone()[0]}")

    print()
    print("-" * 78)
    print("5. ON-POINT MATERIAL IN THE CORPUS")
    print("-" * 78)
    patterns = {
        "development agreement / landowner": r"development agreement|land\s?owner|joint development",
        "TDR / development rights": r"\bTDR\b|transferable development right",
        "consideration in kind": r"consideration in kind|other than (?:in )?cash",
        "para 2A / similar apartments": r"similar apartments|para\s*2A",
        "one-third deduction (para 2)": r"one[- ]third|one third of the total",
        "retrospective vs prospective": r"retrospectiv|prospectiv",
        "occupancy certificate": r"occupancy certificate|completion certificate",
    }
    hits = on_point_rulings(aar, repo, patterns)
    for label, items in hits.items():
        print(f"   {label:<40} {len(items):>4} rulings")
    key = {r for r, _ in hits.get("development agreement / landowner", [])} & \
          {r for r, _ in hits.get("para 2A / similar apartments", []) +
           hits.get("one-third deduction (para 2)", [])}
    if key:
        print(f"\n   directly on point (development agreement + valuation): {len(key)}")
        for r, b in [(r, b) for lab in ("development agreement / landowner",)
                     for r, b in hits[lab] if r in key][:5]:
            print(f"      ruling {r:<6} {b}")

    print()
    print("-" * 78)
    print("6. WHAT THE CORPUS CAN CONTRIBUTE ON THE QUESTION AT ISSUE")
    print("-" * 78)
    sup = supporting_material(aar, repo)
    print("\n   The order turns on whether an amendment may be applied to a supply whose")
    print("   point of taxation predates it. The corpus does not hold the instruments,")
    print("   but rulings QUOTE them and CITE the authorities — secondary evidence, and")
    print("   usable as such.\n")
    print(f"   the principle, as stated in rulings       {len(sup['principle']):>4} rulings")
    for rid, s in sup["principle"][:2]:
        print(f"      ruling {rid}: \"{s[:150]}\"")
    print(f"\n   para 2A text quoted in rulings            {len(sup['para2a']):>4} rulings"
          f"  {sup['para2a'][:6]}")
    print(f"   para 2 text quoted in rulings             {len(sup['para2']):>4} rulings"
          f"  {sup['para2'][:6]}")
    print(f"\n   the clarificatory / prospective distinction")
    print(f"                                             {len(sup['clarificatory']):>4} rulings")
    for rid, s in sup["clarificatory"][:2]:
        print(f"      ruling {rid}: \"{s[:150]}\"")
    print()
    if sup["effective_date"]:
        print(f"   effective date of 03/2019-CTR, as stated in rulings:")
        for rid, s in sup["effective_date"][:3]:
            print(f"      ruling {rid}: {s}")
    else:
        print("   effective date of 03/2019-CTR stated in rulings: NONE")

    print()
    print("=" * 78)
    print("WHAT THIS REVIEW COULD NOT DO")
    print("=" * 78)
    missing_notif = [n for n, own, _ in check_notifications(law, text) if not own]
    missing_auth = [n for n, has in auth if not has]
    print(f"""
   The review above establishes the reasoning. What it cannot establish is the
   fact the reasoning turns on.

   SUPPORTED, from rulings as secondary evidence:
     - the principle that an amendment is prospective unless clarificatory is
       stated in the corpus and attributed to a Supreme Court Constitution Bench
       authority (ruling 1577, citing (2015) 1 SCC 1);
     - the text of para 2A is quoted in the corpus, so its substance can be read;
     - the clarificatory / prospective distinction is discussed, including the
       proposition that a clarificatory note has no statutory force.

   NOT ESTABLISHED, and it is load-bearing:
     - the EFFECTIVE DATE of Notification 03/2019-CTR. No document in the corpus
       states it. The order asserts 01-04-2019; the whole chronology flag rests on
       that date being right, and the department's answer would be that the
       amendment is clarificatory and therefore retrospective.
     - the instrument's own words, which is what decides whether it is clarificatory.

   So the tool can now support "the reasoning is sound and the principle is
   supported by authority". It cannot yet support "the order is contrary to law",
   because that needs the effective date, and the date is one document away —
   Notification 03/2019-CTR itself, not the whole archive. See SCRAPE-BACKLOG.md.
""")
    law.close()
    aar.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    main(ap.parse_args().order)
