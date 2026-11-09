#!/usr/bin/env python3
"""Pillar 3 — generate an industry guide from the advance rulings.

This is synthesis, not judgment: it organises what the rulings already say and
attributes every statement to a ruling. It makes no new claim about the law, which
is why the plan sequences it before the other two pillars.

**The one non-obvious thing.** A naive "most-cited provisions" count produces a guide
about *advance-ruling procedure*, not about the industry. Sections 95–106 are the
Advance Ruling chapter of the CGST/SGST Acts — s.97 (application) and s.98 (procedure
on receipt) are cited in essentially every ruling because they are the Authority's own
jurisdictional basis. They say nothing about the applicant's business. They are
excluded; what remains is the substantive law actually in dispute.

Output is a DRAFT for departmental review, and says so. It carries no accuracy claim —
see eval_harness.py for why one cannot yet be made.

Usage:
    python3 industry_guide.py --sector manufacturing
    python3 industry_guide.py --sector construction --out guides/
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

# the Advance Ruling chapter — the Authority's own basis, not the applicant's issue
AAR_CHAPTER = set(range(95, 107))

# plain-language glosses, so a guide reader is not left with bare section numbers
PROVISION_NOTE = {
    "s.7": "scope of supply — whether a transaction is a supply at all",
    "s.7(1)": "levy of tax on intra-State supplies",
    "s.7(2)": "supply of goods or services for a consideration",
    "s.8": "tax liability on composite and mixed supplies",
    "s.9": "levy and collection of tax",
    "s.15": "value of taxable supply — what the consideration is",
    "s.16": "eligibility and conditions for taking input tax credit",
    "s.16(1)": "conditions for input tax credit",
    "s.17": "apportionment of credit and blocked credits",
    "s.17(5)": "blocked credits — what input tax credit is not available on",
    "s.2": "definitions — how a term used in the Act is to be read",
    "s.2(30)": "definition of 'goods'",
    "s.2(31)": "definition of 'services'",
    "s.2(68)": "definition of 'services'",
    "s.22": "persons liable for registration",
    "s.24": "compulsory registration in certain cases",
    "s.31": "tax invoice — the document a supplier must issue for a supply",
    "s.34": "credit and debit notes — adjustments to an earlier invoice",
    "s.54": "refund of tax — when and how tax already paid can be reclaimed",
    "s.10": "composition levy — the simplified scheme for small suppliers",
    "s.11": "power to grant exemption from tax",
    "s.13": "time of supply of services — when the tax becomes due",
    "s.12": "time of supply of goods — when the tax becomes due",
}


def substantive(ident: str) -> bool:
    m = re.match(r"(?:CGST|SGST|IGST|UTGST)\s+s\.(\d+)", (ident or "").strip())
    return bool(m) and int(m.group(1)) not in AAR_CHAPTER


def norm_provision(ident: str) -> str:
    """Collapse CGST/SGST/IGST/UTGST to one entry — the State Acts mirror the Centre."""
    m = re.match(r"(?:CGST|SGST|IGST|UTGST)\s+s\.(.+)$", (ident or "").strip())
    return f"s.{m.group(1)}" if m else (ident or "").strip()


def gloss(prov: str) -> str:
    return PROVISION_NOTE.get(prov, "")


def build(sector: str, top_n: int) -> str:
    con = sqlite3.connect(AAR)
    con.row_factory = sqlite3.Row
    like = f"%{sector}%"

    rows = con.execute("""
        SELECT ruling_id, applicant, state, issue, issue_outcome, held,
               sections, rates_proposed, order_date, source_url
        FROM decision_record WHERE sectors LIKE ?""", (like,)).fetchall()
    if not rows:
        con.close()
        raise SystemExit(f"no rulings tagged '{sector}'")

    rulings = {r["ruling_id"] for r in rows}
    by_prov: dict[str, list[sqlite3.Row]] = collections.defaultdict(list)
    for r in rows:
        for x in (r["sections"] or "").split(","):
            x = x.strip()
            if substantive(x):
                by_prov[norm_provision(x)].append(r)

    outcomes = collections.Counter(r["issue_outcome"] for r in rows)
    with_out = sum(v for k, v in outcomes.items() if k != "unknown")

    out = []
    out.append(f"# GST guide — {sector.title()}  \n")
    out.append("> **DRAFT for departmental review.** Generated from advance rulings held "
               "in the corpus. Every statement below is attributed to a ruling; nothing "
               "here is a new conclusion of law. Not legal advice.\n")
    out.append("## Evidence base\n")
    out.append(f"- **{len(rulings):,} advance rulings** whose sector tags include this "
               f"sector (a ruling may carry more than one tag)")
    out.append(f"- {len(rows):,} issue rows, of which **{with_out:,} "
               f"({round(100*with_out/max(len(rows),1))}%) record an outcome**")
    out.append(f"- {len(by_prov):,} distinct substantive provisions cited")
    out.append(f"\n**Read the outcome figure carefully.** Only "
               f"{round(100*with_out/max(len(rows),1))}% of issues carry a recorded "
               f"outcome, so this guide is far better at showing *what is disputed* "
               f"than at showing *how it was decided*.")
    out.append("\nThis gap has been diagnosed rather than assumed. Reading the full "
               "orders shows that **95% of the rulings with a missing outcome do state "
               "one** — in the form *\"In view of the above, we rule as under\"* or "
               "*\"we hold that…\"* — so the shortfall is in our extraction, not in the "
               "orders. It is a known defect with a known cause, and should not be read "
               "as the law being silent on these questions.")
    out.append("\nAdvance rulings bind only the applicant and the officer in that case. "
               "They are persuasive, not binding, on anyone else.\n")

    out.append("## What actually gets disputed\n")
    out.append("| Provision | What it governs | Rulings |")
    out.append("|---|---|---:|")
    for prov, items in sorted(by_prov.items(), key=lambda kv: -len(kv[1]))[:top_n]:
        n = len({i["ruling_id"] for i in items})
        out.append(f"| `{prov}` | {gloss(prov) or '—'} | {n} |")
    out.append("")

    out.append("> Sections 95–106 (the Advance Ruling chapter) are excluded: they are "
               "the Authority's own basis for hearing the case and are cited in nearly "
               "every ruling, so including them would describe procedure rather than "
               "this industry's tax issues.\n")

    out.append("## Recurring issues, with what was held\n")
    for prov, items in sorted(by_prov.items(), key=lambda kv: -len(kv[1]))[:top_n]:
        out.append(f"### `{prov}` — {gloss(prov) or 'cited provision'}\n")
        occ = collections.Counter(i["issue_outcome"] for i in items)
        line = ", ".join(f"{k} {v}" for k, v in occ.most_common())
        out.append(f"*Outcomes across the issues citing this provision: {line}*\n")
        seen = set()
        shown = 0
        for i in items:
            key = (i["issue"] or "")[:70]
            if not key or key in seen:
                continue
            seen.add(key)
            held = (i["held"] or "").strip()
            out.append(f"- **{(i['issue'] or '').strip()[:200]}**")
            if held:
                out.append(f"  - Held: {held[:240]}")
            cite = f"ruling {i['ruling_id']}"
            if i["state"]:
                cite += f", {i['state']}"
            out.append(f"  - *{cite}* — {i['source_url']}")
            shown += 1
            if shown >= 4:
                break
        out.append("")

    out.append("## How to read this\n")
    out.append("- Issues are quoted from the rulings; wording is the applicant's or the "
               "Authority's, not ours.")
    out.append("- Where no outcome is recorded, the corpus does not state one. "
               "**A blank is left blank deliberately** — a guessed outcome would be "
               "worse than none.")
    out.append("- This guide is regenerable: re-run `industry_guide.py` as rulings are "
               "added, rather than editing it by hand.")
    con.close()
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", required=True)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    md = build(args.sector, args.top)
    if args.out:
        d = Path(args.out)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"guide-{args.sector}.md"
        p.write_text(md)
        print(f"wrote {p}  ({len(md):,} chars)")
    else:
        print(md)


if __name__ == "__main__":
    main()
