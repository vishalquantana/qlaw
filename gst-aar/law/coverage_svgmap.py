#!/usr/bin/env python3
"""Interactive SVG map of India with state GST-coverage colours + hover tooltips.

Boundary paths live in `india-paths.ts` next to this file (ISC, via MAPSVG - see
credit footer). They used to be read from /tmp, which meant the "regenerable"
map was not actually regenerable after a reboot; the repo copy is now the source
of truth and /tmp is only a fallback.

State colours come from files on disk; the layer totals come from law.db and
aar.db so the page cannot drift from the corpus it advertises.

Usage: python3 coverage_svgmap.py   (writes gst-aar/coverage-svgmap.html)
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent          # gst-aar/
STAGE = ROOT / "data" / "law" / "staging"
LAW_DB = ROOT / "data" / "law" / "law.db"
AAR_DB = ROOT / "data" / "aar.db"
OUT = ROOT / "coverage-svgmap.html"
PATHS_TS = Path(__file__).parent / "india-paths.ts"
PATHS_TS_FALLBACK = Path("/tmp/paths.ts")

NAMES = {
    'AN': 'Andaman & Nicobar', 'AP': 'Andhra Pradesh', 'AR': 'Arunachal Pradesh',
    'AS': 'Assam', 'BR': 'Bihar', 'CH': 'Chandigarh', 'CT': 'Chhattisgarh',
    'DD': 'Dadra & Nagar Haveli', 'DL': 'Delhi', 'DN': 'Daman & Diu', 'GA': 'Goa',
    'GJ': 'Gujarat', 'HP': 'Himachal Pradesh', 'HR': 'Haryana', 'JH': 'Jharkhand',
    'JK': 'Jammu & Kashmir', 'KA': 'Karnataka', 'KL': 'Kerala', 'LA': 'Ladakh',
    'LD': 'Lakshadweep', 'MH': 'Maharashtra', 'ML': 'Meghalaya', 'MN': 'Manipur',
    'MP': 'Madhya Pradesh', 'MZ': 'Mizoram', 'NL': 'Nagaland', 'OR': 'Odisha',
    'PB': 'Punjab', 'PY': 'Puducherry', 'RJ': 'Rajasthan', 'SK': 'Sikkim',
    'TG': 'Telangana', 'TN': 'Tamil Nadu', 'TR': 'Tripura', 'UP': 'Uttar Pradesh',
    'UT': 'Uttarakhand', 'WB': 'West Bengal',
}
DIR_OF = {'AP': 'andhra-pradesh', 'AS': 'assam', 'BR': 'bihar',
          'CT': 'chhattisgarh', 'DL': 'delhi', 'GJ': 'gujarat', 'HR': 'haryana',
          'KA': 'karnataka', 'KL': 'kerala', 'MH': 'maharashtra', 'OR': 'odisha',
          'PB': 'punjab', 'RJ': 'rajasthan', 'TG': 'telangana',
          'TN': 'tamil-nadu', 'UP': 'uttar-pradesh', 'WB': 'west-bengal'}

# Reachable-blocked states: a harvester exists but the portal cannot be reached
# or is login-walled. Named here so the map never implies we checked.
BLOCKED = {
    'WB': 'portal unreachable from the harvesting host',
    'BR': 'login-walled; e-Gazette fallback not yet built',
}
COLORS = {"harvested": "#16a34a", "partial": "#d97706", "blocked": "#dc2626",
          "indiacode": "#0f766e", "pending": "#e2e8f0"}
LABELS = {"harvested": "dedicated feed, harvested",
          "partial": "dedicated feed, partial",
          "blocked": "portal blocked",
          "indiacode": "held via India Code",
          "pending": "nothing held yet"}


# Portal-harvested feeds, one kind per state. India Code material is counted via
# the `state:<name>` tag instead, so the two never overlap.
KIND_BY_CODE = {
    "TG": "tg_notification", "MH": "mh_notification", "AP": "ap_notification",
    "OR": "od_notification", "RJ": "rj_notification", "GJ": "gj_notification",
    "DL": "dl_notification", "UP": "up_notification", "WB": "wb_notification",
    "AS": "as_notification", "TN": "tn_notification", "KA": "ka_notification",
    "CT": "cg_notification", "HR": "hr_notification", "KL": "kl_notification",
    "PB": "pb_notification", "BR": "br_notification",
}


def documents_for(con: sqlite3.Connection, code: str) -> int:
    """Documents held for a state: portal feed by kind, India Code by tag."""
    total = 0
    name = NAMES.get(code)
    if name:
        total += con.execute(
            "SELECT COUNT(*) FROM documents d JOIN law_tags t ON t.doc_id = d.id"
            " WHERE t.tag = ?", (f"state:{name}",)).fetchone()[0]
    kind = KIND_BY_CODE.get(code)
    if kind:
        total += con.execute(
            "SELECT COUNT(*) FROM documents WHERE kind = ?", (kind,)).fetchone()[0]
    return total


def status_of(con: sqlite3.Connection, code: str) -> tuple[str, int]:
    """Distinguish a state we harvest from its own portal from one we only hold
    because India Code carries it — the two mean different things to a reader."""
    n = documents_for(con, code)
    if code in BLOCKED:
        return "blocked", n
    if KIND_BY_CODE.get(code):          # a dedicated portal feed exists
        if n >= 10:
            return "harvested", n
        return ("partial", n) if n > 0 else ("partial", 0)
    if n > 0:                           # no feed; material comes from India Code
        return "indiacode", n
    return "pending", 0
    return "partial", 0


def _scalar(con, sql, default=0):
    try:
        row = con.execute(sql).fetchone()
        return row[0] if row and row[0] is not None else default
    except sqlite3.Error:
        return default


def layer_totals() -> list[tuple[str, int]]:
    """(layer, count) straight from the databases the product serves from."""
    out = []
    if LAW_DB.exists():
        con = sqlite3.connect(LAW_DB)
        try:
            out.append(("State GST notifications", _scalar(con,
                "SELECT COUNT(*) FROM documents WHERE kind LIKE '%\\_notification' ESCAPE '\\'")))
            out.append(("Central notifications & circulars", _scalar(con,
                "SELECT COUNT(*) FROM documents WHERE kind IN ('notification','circular')")))
            out.append(("CBIC statute hierarchy (acts, chapters, sections, rules, forms)",
                _scalar(con,
                "SELECT COUNT(*) FROM documents WHERE kind LIKE 'cbic\\_%' ESCAPE '\\'")))
            out.append(("Council minutes & papers", _scalar(con,
                "SELECT COUNT(*) FROM documents WHERE kind LIKE 'council%'")))
            out.append(("Bills & Acts", _scalar(con,
                "SELECT COUNT(*) FROM documents WHERE kind IN ('bill','act')")))
        finally:
            con.close()
    if AAR_DB.exists():
        con = sqlite3.connect(AAR_DB)
        try:
            out.append(("AAR / AAAR advance rulings", _scalar(con,
                "SELECT COUNT(*) FROM rulings")))
        finally:
            con.close()
    return out


def main() -> None:
    src = PATHS_TS if PATHS_TS.exists() else PATHS_TS_FALLBACK
    ts = src.read_text()
    paths = dict(re.findall(r"^\s*([A-Z]{2}): `(.*?)`,?\s*$", ts, re.M | re.S))
    assert len(paths) >= 34, f"only {len(paths)} paths parsed from {src}"
    assert len(paths) == len(set(paths)), "duplicate state codes in paths file"

    total, states = 0, []
    con = sqlite3.connect(LAW_DB) if LAW_DB.exists() else None
    for code, d in sorted(paths.items()):
        st, n = status_of(con, code) if con else ("pending", 0)
        total += n
        states.append((code, st, n))
    if con:
        con.close()

    harvested = sum(1 for _, st, _ in states if st == "harvested")
    partial = sum(1 for _, st, _ in states if st == "partial")
    blocked = sum(1 for _, st, _ in states if st == "blocked")
    indiacode = sum(1 for _, st, _ in states if st == "indiacode")
    pending = sum(1 for _, st, _ in states if st == "pending")
    with_feed = sum(1 for c in paths if KIND_BY_CODE.get(c))

    paths_svg = "\n".join(
        f'<path id="st-{code}" d="{d}" fill="{COLORS[st]}" data-name="{NAMES.get(code, code)}"'
        f' data-count="{n}" data-status="{LABELS[st]}"'
        f'><title>{NAMES.get(code, code)} — {n} documents ({LABELS[st]})</title></path>'
        for code, st, n in states for d in [paths[code]])

    legend = "".join(
        f'<span class="lg"><i style="background:{COLORS[s]}"></i>{LABELS[s]}'
        f" ({c})</span>"
        for s, c in (("harvested", harvested), ("partial", partial),
                     ("indiacode", indiacode), ("blocked", blocked),
                     ("pending", pending)))

    layers = layer_totals()
    layer_rows = "".join(
        f"<tr><td>{name}</td><td class=num>{n:,}</td></tr>" for name, n in layers)
    layer_total = sum(n for _, n in layers)

    top = "".join(
        f"<tr><td>{NAMES.get(c, c)}</td><td class=num>{n:,}</td>"
        f"<td>{LABELS[s]}</td></tr>"
        for c, s, n in sorted(states, key=lambda x: -x[2])[:10])

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GST State Coverage — Interactive Map</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1040px;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.4rem;letter-spacing:-.4px;margin-bottom:.2rem}}
h2{{font-size:.95rem;text-transform:uppercase;letter-spacing:.06em;color:#666;margin:1.4rem 0 .5rem}}
.sub{{color:#555;font-size:.9rem;margin-top:0}}
.wrap{{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}}
svg.india{{width:min(470px,100%);height:auto;background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px}}
svg.india path{{stroke:#fff;stroke-width:1.2;cursor:pointer;transition:fill .15s,opacity .15s,transform .15s;transform-box:fill-box;transform-origin:center}}
svg.india path:hover{{opacity:.85;transform:scale(1.03)}}
#tip{{position:fixed;pointer-events:none;background:#16181d;color:#fff;font-size:12.5px;
padding:8px 12px;border-radius:9px;box-shadow:0 8px 24px rgba(0,0,0,.25);display:none;z-index:50;max-width:260px}}
#tip b{{display:block;font-size:13px}}#tip span{{color:#cbd5e1}}
.side{{flex:1;min-width:260px}}
.cards{{display:flex;gap:.8rem;margin:.6rem 0;flex-wrap:wrap}}
.card{{border:1px solid #e5e7eb;border-radius:8px;padding:.6rem 1rem}}
.card b{{font-size:1.25rem;display:block}}.card span{{font-size:.78rem;color:#555}}
.lg{{font-size:.82rem;margin-right:12px;display:inline-block;margin-bottom:4px}}
.lg i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-1px}}
table{{border-collapse:collapse;font-size:.85rem;margin-top:.4rem;width:100%}}
td,th{{border:1px solid #e5e7eb;padding:.35rem .6rem;text-align:left}}
th{{background:#f8fafc;font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.credit,.note{{font-size:.78rem;color:#777}}
</style></head><body>
<h1>GST law coverage across India</h1>
<p class="sub">Official <code>.gov.in</code> / <code>.nic.in</code> sources only · hover any state for its file count</p>
<div class="wrap">
<svg class="india" viewBox="-114 -50.4 611.9 695.7" role="img" aria-label="India coverage map">
{paths_svg}
</svg>
<div class="side">
<div class="cards">
<div class="card"><b>{total:,}</b><span>state documents held</span></div>
<div class="card"><b>{harvested + partial}/{with_feed}</b><span>state feeds live</span></div>
<div class="card"><b>{blocked}</b><span>portals blocked</span></div>
</div>
<div>{legend}</div>
<table><tr><th>State</th><th class=num>Files</th><th>Status</th></tr>
{top}
</table>
<p class="note">Top 10 shown · {with_feed} states and UTs publish a separate state feed; the rest
administer GST under the central Acts.</p>
</div></div>

<h2>Corpus by layer</h2>
<table><tr><th>Layer</th><th class=num>Documents</th></tr>
{layer_rows}
<tr><td><b>Total</b></td><td class=num><b>{layer_total:,}</b></td></tr>
</table>

<div id="tip"></div>
<script>
const tip = document.getElementById('tip');
document.querySelectorAll('svg.india path').forEach(p => {{
  p.addEventListener('mousemove', e => {{
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top = (e.clientY + 14) + 'px';
    tip.innerHTML = '<b>' + p.dataset.name + '</b>' + p.dataset.count + ' documents · <span>' + p.dataset.status + '</span>';
  }});
  p.addEventListener('mouseleave', () => tip.style.display = 'none');
}});
</script>
<p class="credit">Map boundaries: react-svgmap-india (ISC) via MAPSVG · counts read live from law.db and aar.db</p>
</body></html>"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({total:,} state documents, {harvested} harvested, "
          f"{partial} partial, {indiacode} via India Code, {blocked} blocked, "
          f"{pending} pending, {layer_total:,} documents total)")


if __name__ == "__main__":
    main()
