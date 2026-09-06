#!/usr/bin/env python3
"""Interactive SVG map of India with state GST-coverage colors + hover tooltips.

Boundary paths from react-svgmap-india (ISC, via MAPSVG) — see credit footer.
Coverage counted live from staging dirs.
Usage: python3 coverage_svgmap.py   (writes gst-aar/coverage-svgmap.html)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
STAGE = ROOT / "data" / "law" / "staging"
OUT = ROOT / "coverage-svgmap.html"
PATHS_TS = Path("/tmp/paths.ts")

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
DIR_OF = {'AS': 'assam', 'BR': 'bihar', 'CT': 'chhattisgarh', 'DL': 'delhi',
          'GJ': 'gujarat', 'HR': 'haryana', 'KA': 'karnataka', 'KL': 'kerala',
          'MH': 'maharashtra', 'OR': 'odisha', 'PB': 'punjab', 'RJ': 'rajasthan',
          'TG': 'telangana', 'TN': 'tamil-nadu', 'UP': 'uttar-pradesh', 'WB': 'west-bengal'}
COLORS = {"strong": "#16a34a", "growing": "#d97706", "sampled": "#60a5fa",
          "blocked": "#dc2626", "pending": "#cbd5e1"}


def status_of(code: str) -> tuple[str, int]:
    if code == "BR":
        return "blocked", 0
    d = DIR_OF.get(code)
    n = sum(1 for _ in (STAGE / d).glob("*.pdf")) if d and (STAGE / d).exists() else 0
    if n >= 400:
        return "strong", n
    if n >= 10:
        return "growing", n
    if n > 0:
        return "sampled", n
    return "pending", 0


def main() -> None:
    ts = PATHS_TS.read_text()
    paths = dict(re.findall(r"^\s*([A-Z]{2}): `(.*?)`,?\s*$", ts, re.M | re.S))
    assert len(paths) >= 34, f"only {len(paths)} paths parsed"
    total, states = 0, []
    for code, d in sorted(paths.items()):
        st, n = status_of(code)
        total += n
        states.append((code, st, n))
    paths_svg = "\n".join(
        f'<path id="st-{code}" d="{d}" fill="{COLORS[st]}" data-name="{NAMES.get(code, code)}"'
        f' data-count="{n}" data-status="{st}"><title>{NAMES.get(code, code)} — {n} files ({st})</title></path>'
        for code, st, n in states for d in [paths[code]])
    legend = "".join(
        f'<span class="lg"><i style="background:{COLORS[s]}"></i>{s}</span>'
        for s in ("strong", "growing", "sampled", "blocked", "pending"))
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>GST State Coverage — Interactive Map</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.4rem;letter-spacing:-.4px}}.sub{{color:#555;font-size:.9rem}}
.wrap{{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}}
svg.india{{width:min(480px,100%);height:auto;background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px}}
svg.india path{{stroke:#fff;stroke-width:1.2;cursor:pointer;transition:fill .15s,opacity .15s,transform .15s;transform-box:fill-box;transform-origin:center}}
svg.india path:hover{{opacity:.85;transform:scale(1.03)}}
#tip{{position:fixed;pointer-events:none;background:#16181d;color:#fff;font-size:12.5px;
padding:8px 12px;border-radius:9px;box-shadow:0 8px 24px rgba(0,0,0,.25);display:none;z-index:50;max-width:260px}}
#tip b{{display:block;font-size:13px}}#tip span{{color:#cbd5e1;text-transform:capitalize}}
.side{{flex:1;min-width:240px}}
.cards{{display:flex;gap:.8rem;margin:.6rem 0;flex-wrap:wrap}}
.card{{border:1px solid #e5e7eb;border-radius:8px;padding:.6rem 1rem}}
.card b{{font-size:1.25rem;display:block}}.card span{{font-size:.78rem;color:#555}}
.lg{{font-size:.82rem;margin-right:12px;text-transform:capitalize}}
.lg i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px}}
table{{border-collapse:collapse;font-size:.85rem;margin-top:1rem}}
td,th{{border:1px solid #e5e7eb;padding:.35rem .6rem;text-align:left}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.credit,.note{{font-size:.78rem;color:#777}}
</style></head><body>
<h1>GST legislation coverage across India</h1>
<p class="sub">Official state sources only · hover any state for its file count</p>
<div class="wrap">
<svg class="india" viewBox="-114 -50.4 611.9 695.7" role="img" aria-label="India coverage map">
{paths_svg}
</svg>
<div class="side">
<div class="cards"><div class="card"><b>{total:,}</b><span>state files held</span></div>
<div class="card"><b>15/16</b><span>states harvesting</span></div></div>
<div>{legend}</div>
<table><tr><th>State</th><th>Files</th><th>Status</th></tr>
{"".join(f"<tr><td>{NAMES.get(c, c)}</td><td class=num>{n:,}</td><td style=text-transform:capitalize>{s}</td></tr>" for c, s, n in sorted(states, key=lambda x: -x[2])[:10])}
</table>
<p class="note">Top 10 shown · regenerate: <code>python3 gst-aar/law/coverage_svgmap.py</code></p>
</div></div>
<div id="tip"></div>
<script>
const tip = document.getElementById('tip');
document.querySelectorAll('svg.india path').forEach(p => {{
  p.addEventListener('mousemove', e => {{
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top = (e.clientY + 14) + 'px';
    tip.innerHTML = '<b>' + p.dataset.name + '</b>' + p.dataset.count + ' files · <span>' + p.dataset.status + '</span>';
  }});
  p.addEventListener('mouseleave', () => tip.style.display = 'none');
}});
</script>
<p class="credit">Map boundaries: react-svgmap-india (ISC) via MAPSVG · coverage counted live from the corpus</p>
</body></html>"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({total:,} files, {len(paths)} states)")


if __name__ == "__main__":
    main()
