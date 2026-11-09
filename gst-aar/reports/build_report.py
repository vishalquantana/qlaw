#!/usr/bin/env python3
"""Build the client report HTML: inject the India coverage map + state table.

Reads `report.template.html`, replaces the `<!--COVERAGE-MAP-->` marker with a
colour-coded India SVG, a legend, and a coverage-by-state table, and writes
`gst-corpus-status-report.html`. The PDF is then rendered from that by Chrome.

Boundary paths come from `gst-aar/law/india-paths.ts` (react-svgmap-india, ISC) —
the same source the marketing map uses, so the two cannot disagree.

Usage: python3 build_report.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent
PATHS_TS = HERE.parent / "law" / "india-paths.ts"
TEMPLATE = HERE / "report.template.html"
OUT = HERE / "gst-corpus-status-report.html"

# code -> (display name, documents held, status)
# Status: covered (own feed) | indiacode (held via India Code) | blocked | none
COVERAGE = {
    # dedicated state feeds
    "TG": ("Telangana", 1191, "covered"),
    "MH": ("Maharashtra", 761, "covered"),
    "AP": ("Andhra Pradesh", 704, "covered"),
    "OR": ("Odisha", 613, "covered"),
    "RJ": ("Rajasthan", 588, "covered"),
    "GJ": ("Gujarat", 566, "covered"),
    "DL": ("Delhi", 476, "covered"),
    "UP": ("Uttar Pradesh", 432, "covered"),
    "AS": ("Assam", 80, "covered"),
    "TN": ("Tamil Nadu", 70, "covered"),
    "KA": ("Karnataka", 56, "covered"),
    "CT": ("Chhattisgarh", 42, "covered"),
    "HR": ("Haryana", 40, "covered"),
    "KL": ("Kerala", 21, "covered"),
    "PB": ("Punjab", 15, "covered"),
    # held through India Code; no dedicated feed yet
    "JH": ("Jharkhand", 534, "indiacode"),
    "MP": ("Madhya Pradesh", 415, "indiacode"),
    "TR": ("Tripura", 188, "indiacode"),
    "AR": ("Arunachal Pradesh", 69, "indiacode"),
    "MZ": ("Mizoram", 19, "indiacode"),
    "NL": ("Nagaland", 12, "indiacode"),
    "CH": ("Chandigarh", 6, "indiacode"),
    "UT": ("Uttarakhand", 5, "indiacode"),
    "ML": ("Meghalaya", 3, "indiacode"),
    "MN": ("Manipur", 3, "indiacode"),
    "GA": ("Goa", 1, "indiacode"),
    "HP": ("Himachal Pradesh", 1, "indiacode"),
    "PY": ("Puducherry", 1, "indiacode"),
    "SK": ("Sikkim", 1, "indiacode"),
    # portal unreachable; material held from before
    "WB": ("West Bengal", 414, "blocked"),
    "BR": ("Bihar", 8, "blocked"),
}
# every remaining polygon on the map is not yet covered
NAMES = {
    "AN": "Andaman & Nicobar Islands", "DD": "Dadra & Nagar Haveli",
    "DN": "Daman & Diu", "JK": "Jammu & Kashmir", "LA": "Ladakh",
    "LD": "Lakshadweep",
}

FILL = {"covered": "#16a34a", "indiacode": "#0f766e", "blocked": "#dc2626",
        "none": "#e2e8f0"}
LABEL = {"covered": "Own feed", "indiacode": "Via India Code",
         "blocked": "Blocked", "none": "Not yet covered"}


def status_of(code: str) -> tuple[str, int]:
    if code in COVERAGE:
        name, n, st = COVERAGE[code]
        return st, n
    return "none", 0


def unit_of(code: str) -> str:
    """Dadra & Nagar Haveli and Daman & Diu are one UT but two map polygons."""
    return "DNDD" if code in ("DD", "DN") else code


def build_map(paths: dict[str, str]) -> str:
    parts = []
    for code in sorted(paths):
        st, n = status_of(code)
        nm = COVERAGE.get(code, (NAMES.get(code, code),))[0]
        parts.append(
            f'<path d="{paths[code]}" fill="{FILL[st]}" stroke="#ffffff" '
            f'stroke-width="1.1"><title>{nm}</title></path>')
    return "\n".join(parts)


def main() -> None:
    ts = PATHS_TS.read_text()
    paths = dict(re.findall(r"^\s*([A-Z]{2}): `(.*?)`,?\s*$", ts, re.M | re.S))
    assert len(paths) >= 34, f"only {len(paths)} paths parsed"

    counts = {k: 0 for k in FILL}
    for code in {unit_of(c) for c in paths}:
        counts[status_of(code)[0]] += 1
    covered_rows = sorted(
        ((nm, n, st) for nm, n, st in COVERAGE.values()), key=lambda r: -r[1])
    not_covered = sorted(
        NAMES.get(u, "Dadra & Nagar Haveli and Daman & Diu" if u == "DNDD" else u)
        for u in {unit_of(c) for c in paths} if status_of(u)[0] == "none")

    legend = "".join(
        f'<div><i style="background:{FILL[k]}"></i>{LABEL[k]} — {counts[k]} '
        f'{"state/UT" if counts[k] == 1 else "states/UTs"}</div>'
        for k in ("covered", "indiacode", "blocked", "none"))

    rows = "".join(
        f'<tr><td>{nm}</td><td class="num">{n:,}</td><td>{LABEL[st]}</td></tr>'
        for nm, n, st in covered_rows)
    # split into two side-by-side tables so 31 rows do not force a page break
    half = (len(covered_rows) + 1) // 2
    rows_a = "".join(
        f'<tr><td>{nm}</td><td class="num">{n:,}</td><td>{LABEL[st]}</td></tr>'
        for nm, n, st in covered_rows[:half])
    rows_b = "".join(
        f'<tr><td>{nm}</td><td class="num">{n:,}</td><td>{LABEL[st]}</td></tr>'
        for nm, n, st in covered_rows[half:])
    head = ('<tr><th>State / UT</th><th class="num">Docs</th>'
            '<th>Basis</th></tr>')

    block = f"""<div class="mapblock">
  <div class="mapwrap">
    <svg viewBox="-114 -50.4 611.9 695.7" role="img" aria-label="Coverage across India">
{build_map(paths)}
    </svg>
    <div class="maplegend">{legend}</div>
  </div>
  <div class="mapnote">
    <p><b>Material is held for {counts['covered'] + counts['indiacode'] + counts['blocked']}
    of India's 36 states and union territories</b> — {counts['covered']} harvested from
    the state's own portal, {counts['indiacode']} held through the official India Code
    repository, and {counts['blocked']} where the portal is unreachable but material is
    held.</p>
    <p>A state's own portal is the fresher source, so the India Code states are
    <i>covered</i> rather than <i>complete</i> — that distinction is the next piece of
    work, and it is why the two are coloured separately.</p>
    <p><b>Not yet covered ({len(not_covered)}):</b> {", ".join(not_covered)} —
    union territories that administer GST through central legislation or a
    neighbouring state's Act.</p>
  </div>
</div>
<div class="statetables">
  <table class="statecol">{head}{rows_a}</table>
  <table class="statecol">{head}{rows_b}</table>
</div>"""

    html = TEMPLATE.read_text().replace("<!--COVERAGE-MAP-->", block)
    assert "<!--COVERAGE-MAP-->" not in html, "marker not replaced"
    OUT.write_text(html)
    print(f"wrote {OUT}")
    print(f"  map polygons: {len(paths)}")
    for k in ("covered", "indiacode", "blocked", "none"):
        print(f"  {LABEL[k]:20s} {counts[k]}")
    print(f"  not yet covered list: {len(not_covered)}")


if __name__ == "__main__":
    main()
