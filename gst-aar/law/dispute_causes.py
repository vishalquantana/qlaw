#!/usr/bin/env python3
"""Pillar 2 — a draft taxonomy of why GST disputes arise, with the evidence for it.

The plan says root-cause attribution needs the department to validate the taxonomy
before anything is built on it. This produces that draft, but derives it from the
corpus rather than inventing it: each cause is defined by signals that actually appear
in the issue text and in the provisions cited, and every cause is reported with the
count and examples that support it.

**What this is not.** It is not an attribution of blame. "Drafting ambiguity" is a
conclusion an officer draws from evidence; this surfaces candidate causes and shows its
work so the officer can disagree with a click. Nothing here should be presented as a
finding about the law.

Signals are deliberately transparent — a reader can see exactly why a row was tagged,
which is what makes the draft reviewable rather than a black box.

Usage:
    python3 dispute_causes.py                 # distribution across the corpus
    python3 dispute_causes.py --sector manufacturing
    python3 dispute_causes.py --write         # draft taxonomy doc for review
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

# Each cause: a plain-language gloss, textual signals, and the provisions that
# typically carry it. A row is tagged when either signal fires.
CAUSES: dict[str, dict] = {
    "classification": {
        "gloss": "What the goods or services are, and which tariff entry they fall in",
        "text": [r"\bclassif", r"\bHSN\b", r"\bSAC\b", r"\bheading\b", r"\btariff\b",
                 r"\bsub-?heading\b", r"\bSchedule\b", r"\bchapter\b"],
        "sections": ["s.2(30)", "s.2(31)", "s.2(68)"],
    },
    "scope_of_supply": {
        "gloss": "Whether the transaction is a supply at all, and under which limb",
        "text": [r"\bsupply\b", r"\bschedule\s+III\b", r"\bwhether.{0,20}supply\b",
                 r"\boutside the scope\b", r"\bneither goods nor services\b"],
        "sections": ["s.7", "s.7(1)", "s.7(2)", "s.7(1)(a)"],
    },
    "composite_or_mixed": {
        "gloss": "Whether a bundle of supplies is one supply or several, and which is principal",
        "text": [r"\bcomposite\b", r"\bmixed supply\b", r"\bprincipal supply\b",
                 r"\bnaturally bundled\b"],
        "sections": ["s.8"],
    },
    "valuation": {
        "gloss": "What the taxable value is — consideration, inclusions, related parties",
        "text": [r"\bvaluation\b", r"\bvalue of supply\b", r"\btransaction value\b",
                 r"\bconsideration\b", r"\brelated part", r"\bsubsid", r"\bdiscount\b"],
        "sections": ["s.15"],
    },
    "input_tax_credit": {
        "gloss": "Whether credit is available, and whether it is blocked",
        "text": [r"\binput tax credit\b", r"\bITC\b", r"\bblocked credit\b",
                 r"\bcredit\b.{0,25}\b(?:avail|eligib|deni)", r"\breversal\b"],
        "sections": ["s.16", "s.16(1)", "s.17", "s.17(5)"],
    },
    "rate_and_exemption": {
        "gloss": "Which rate applies, or whether an exemption or concessional rate covers it",
        "text": [r"\brate\b", r"\bexempt", r"\bconcessional\b", r"\bnotification\b",
                 r"\bNil rated\b"],
        "sections": ["s.9", "s.11"],
    },
    "place_of_supply": {
        "gloss": "Which State the supply belongs to — intra-State or inter-State",
        "text": [r"\bplace of supply\b", r"\binter-state\b", r"\bintra-state\b",
                 r"\bIGST\b.{0,25}\bCGST\b"],
        "sections": [],
    },
    "time_of_supply": {
        "gloss": "When the tax became due — the point of taxation",
        "text": [r"\btime of supply\b", r"\bpoint of taxation\b", r"\bwhen.{0,20}tax.{0,20}payable\b"],
        "sections": ["s.12", "s.13"],
    },
    "registration": {
        "gloss": "Whether the person was required to register, or a registration should be cancelled",
        "text": [r"\bregistration\b", r"\bregistered person\b", r"\bcancellation of registration\b"],
        "sections": ["s.22", "s.24", "s.29", "s.30"],
    },
    "refund": {
        "gloss": "Whether tax paid can be reclaimed, and within what time",
        "text": [r"\brefund\b", r"\bunutilised\b", r"\bzero-rated\b", r"\bexport\b"],
        "sections": ["s.54", "s.55"],
    },
    "reverse_charge": {
        "gloss": "Whether the recipient, rather than the supplier, must pay",
        "text": [r"\breverse charge\b", r"\bRCM\b", r"\brecipient.{0,25}\bliable\b"],
        "sections": ["s.9(3)", "s.9(4)"],
    },
    "procedure_and_limitation": {
        "gloss": "Whether the Authority could hear the matter at all, and whether it was in time",
        "text": [r"\bmaintainab", r"\bjurisdiction\b", r"\blimitation\b", r"\btime-?barred\b",
                 r"\bnot maintainable\b", r"\boutside the purview\b", r"\bwithdrawn\b"],
        "sections": [],
    },
    "transitional": {
        "gloss": "Whether credit or liability carried over from the pre-GST regime",
        "text": [r"\btransitional\b", r"\bcarry forward\b", r"\bcarried forward\b",
                 r"\bmigrat", r"\bTRAN-?1\b", r"\bappointed day\b"],
        "sections": ["s.140", "s.141", "s.142"],
    },
    "compliance_and_invoicing": {
        "gloss": "Whether the paperwork — invoice, credit note, e-way bill — was correct",
        "text": [r"\binvoice\b", r"\bcredit note\b", r"\bdebit note\b", r"\be-?way bill\b",
                 r"\bdelivery challan\b", r"\bbill of supply\b"],
        "sections": ["s.31", "s.34"],
    },
}
COMPILED = {k: [re.compile(p, re.I) for p in v["text"]] for k, v in CAUSES.items()}


def classify(issue: str, sections: str) -> list[str]:
    """Tag an issue with every cause whose signals fire. Multi-label on purpose —
    a dispute about a composite supply's valuation is genuinely both."""
    issue = issue or ""
    have = {s.strip() for s in (sections or "").split(",") if s.strip()}
    bare = {re.sub(r"^(?:CGST|SGST|IGST|UTGST)\s+", "", s) for s in have}
    out = []
    for cause, spec in CAUSES.items():
        if any(rx.search(issue) for rx in COMPILED[cause]):
            out.append(cause)
            continue
        if bare & set(spec["sections"]):
            out.append(cause)
    return out


def run(sector: str = "") -> None:
    con = sqlite3.connect(AAR)
    where = "WHERE sectors LIKE ?" if sector else ""
    args = (f"%{sector}%",) if sector else ()
    rows = con.execute(f"""
        SELECT issue, sections, issue_outcome FROM decision_record {where}""",
        args).fetchall()

    counts = collections.Counter()
    outcomes = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    unclassified = 0
    for issue, sections, outcome in rows:
        tags = classify(issue, sections)
        if not tags:
            unclassified += 1
            continue
        for t in tags:
            counts[t] += 1
            outcomes[t][outcome] += 1
            if len(examples[t]) < 3 and issue:
                examples[t].append(issue.strip()[:150])

    total = len(rows)
    label = f"sector '{sector}'" if sector else "the whole corpus"
    print("=" * 70)
    print(f"DISPUTE CAUSES — {label}")
    print("=" * 70)
    print(f"\n  issue rows examined       {total:,}")
    print(f"  tagged with >=1 cause     {total - unclassified:,}  "
          f"({round(100*(total-unclassified)/max(total,1))}%)")
    print(f"  untagged                  {unclassified:,}  "
          f"({round(100*unclassified/max(total,1))}%)")
    print("\n  multi-label: a dispute about a composite supply's valuation is both,")
    print("  so the counts below sum to more than the number of rows.\n")
    print(f"  {'cause':<28} {'rows':>6} {'share':>7}   most common outcome")
    for cause, n in counts.most_common():
        oc = outcomes[cause].most_common(1)
        print(f"  {cause:<28} {n:>6} {round(100*n/max(total,1)):>6}%   "
              f"{oc[0][0] if oc else '-'}")
    print("\n  --- evidence: the first issues tagged to each cause ---")
    for cause, _ in counts.most_common(6):
        print(f"\n  {cause} — {CAUSES[cause]['gloss']}")
        for ex in examples[cause][:2]:
            print(f"     · {ex}")
    con.close()


def clean_signal(pattern: str) -> str:
    """Show a signal as readable text.

    NB `str.strip("\\b^$")` removes those CHARACTERS from both ends, so
    "\\\\bblocked credit\\\\b" came out as "locked credit" and "maintainab" as
    "maintaina" — the doc looked like it had typos. Remove the anchors literally.

    Quantified gaps are rendered as an ellipsis so the published table reads as
    English rather than as a regex: "whether.{0,20}supply" -> "whether … supply".
    """
    s = re.sub(r"\.\{\d+(?:,\d+)?\}", " … ", pattern)
    s = s.replace("\\b", "").replace("\\s+", " ").replace("\\s", " ")
    s = s.replace("^", "").replace("$", "").replace("?", "")
    return re.sub(r"\s+", " ", s).strip()


def write_doc() -> None:
    out = HERE.parent / "DISPUTE-CAUSES.md"
    lines = [
        "# Draft taxonomy of GST dispute causes",
        "",
        "> **DRAFT for departmental validation.** This is not an attribution of blame.",
        "> Each cause is a candidate, derived from signals that appear in the rulings' own",
        "> issue text and cited provisions, and shown with the evidence behind it so it can",
        "> be disagreed with. Nothing here is a finding about the law.",
        "",
        "## Why this exists",
        "",
        "The department asked whether the tool could identify the root causes of common",
        "disputes — bad drafting, misinterpretation — and suggest how to reduce them.",
        "Attribution is an interpretive claim, so the taxonomy has to be agreed before",
        "anything is built on it. This is the draft to agree.",
        "",
        "## The causes",
        "",
        "| Cause | What it covers | Signals used |",
        "|---|---|---|",
    ]
    for cause, spec in CAUSES.items():
        sig = ", ".join(clean_signal(s) for s in spec["text"][:3])
        lines.append(f"| `{cause}` | {spec['gloss']} | {sig} |")
    lines += [
        "",
        "## How to read the counts",
        "",
        "A row is tagged to every cause whose signals fire, so the counts are",
        "multi-label and sum to more than the number of disputes. That is deliberate:",
        "a dispute about whether a composite supply was correctly valued is genuinely",
        "both a composite-supply question and a valuation question, and forcing a single",
        "label would hide that.",
        "",
        "## What is needed from the department",
        "",
        "1. **Are these the right causes?** Particularly whether *drafting ambiguity*",
        "   should be something the tool assigns, or something an officer concludes from",
        "   evidence the tool presents. That distinction changes the design.",
        "2. **Is anything missing?** The signals are visible above so gaps are easy to spot.",
        "3. **Which causes are worth acting on?** A cause that cannot be reduced by any",
        "   practical step is interesting but not actionable.",
        "",
        "## Honest limitations",
        "",
        "- Signals are textual. A dispute about valuation that never uses the word",
        "  \"valuation\" will be missed, and one that mentions it in passing will be",
        "  over-tagged. The untagged share is reported so the size of that is visible.",
        "- **Attribution is not causation.** A count of disputes citing ambiguous drafting",
        "  is not a measure of how much ambiguity costs; it is a measure of where to look.",
        "- Only issues with a recorded outcome can support a claim about how a cause",
        "  resolves, and outcome coverage is incomplete (see PRODUCT-PILLARS.md §2b).",
        "",
        "Generated by `gst-aar/law/dispute_causes.py --write`.",
    ]
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", default="")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.write:
        write_doc()
    else:
        run(a.sector)


if __name__ == "__main__":
    main()
