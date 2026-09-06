#!/usr/bin/env python3
"""Regenerable marketing visual: India cartogram of state GST-legislation coverage.

Counts PDFs on disk per staging dir. Statuses: strong (>=400 files),
growing (>=10), sampled (>0), blocked (Bihar, login-walled), pending (0).
Usage: python3 coverage_map.py   (writes gst-aar/coverage-map.html)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
STAGE = ROOT / "data" / "law" / "staging"
OUT = ROOT / "coverage-map.html"

DIR_OF = {
    "JK": None, "Ladakh": None, "HP": None, "Punjab": "punjab", "Uttarakhand": None,
    "Haryana": "haryana", "Delhi": "delhi", "UP": "uttar-pradesh", "Rajasthan": "rajasthan",
    "Bihar": "bihar", "MP": None, "Gujarat": "gujarat", "Maharashtra": "maharashtra",
    "Chhattisgarh": "chhattisgarh", "Jharkhand": None, "WB": "west-bengal", "Karnataka": "karnataka",
    "Telangana": "telangana", "AP": None, "Odisha": "odisha", "Kerala": "kerala",
    "TN": "tamil-nadu", "Assam": "assam", "NE": None, "Goa": None,
}
ABBR = {"JK": "J&K", "UP": "UP", "MP": "MP", "WB": "WB", "TN": "TN", "AP": "AP", "NE": "NE", "HP": "HP"}

# (name, col, row) on a 7x8 grid approximating India
CELLS = [
    ("JK", 1, 0), ("Ladakh", 2, 0), ("HP", 2, 1),
    ("Punjab", 1, 1), ("Uttarakhand", 3, 1),
    ("Haryana", 1, 2), ("Delhi", 2, 2), ("UP", 3, 2),
    ("Rajasthan", 1, 3), ("MP", 2, 3), ("Bihar", 4, 3),
    ("Gujarat", 0, 4), ("Maharashtra", 1, 4), ("Chhattisgarh", 2, 4),
    ("Jharkhand", 3, 4), ("WB", 4, 4),
    ("Karnataka", 1, 5), ("Telangana", 2, 5), ("AP", 3, 5), ("Odisha", 4, 5),
    ("Kerala", 1, 6), ("TN", 2, 6),
    ("Assam", 5, 5), ("NE", 6, 5), ("Goa", 0, 5),
]


def status_of(name: str) -> tuple[str, int, str]:
    d = DIR_OF.get(name)
    n = sum(1 for _ in (STAGE / d).glob("*.pdf")) if d and (STAGE / d).exists() else 0
    if name == "Bihar":
        return "blocked", 0, "login-walled"
    if n >= 400:
        return "strong", n, f"{n} files"
    if n >= 10:
        return "growing", n, f"{n} files"
    if n > 0:
        return "sampled", n, f"{n} files"
    return "pending", 0, "queued"


COLORS = {"strong": "#16a34a", "growing": "#d97706", "sampled": "#60a5fa",
          "blocked": "#dc2626", "pending": "#cbd5e1"}
BG = {"strong": "#e7f6ef", "growing": "#fdf3e3", "sampled": "#eff6ff",
      "blocked": "#fdecea", "pending": "#f1f5f9"}


def main() -> None:
    boxes = {}
    total = 0
    for name, c, r in CELLS:
        st, n, label = status_of(name)
        total += n
        boxes[(c, r)] = (name, st, n, label)
    cells = ""
    for r in range(8):
        for c in range(7):
            if (c, r) in boxes:
                name, st, n, label = boxes[(c, r)]
                cells += (
                    f'<div class="st" style="grid-column:{c + 1};grid-row:{r + 1};'
                    f'background:{BG[st]};border-color:{COLORS[st]}">'
                    f"<b>{ABBR.get(name, name)}</b><span>{label}</span></div>")
    legend = "".join(
        f'<span class="lg"><i style="background:{COLORS[s]}"></i>{s}</span>'
        for s in ("strong", "growing", "sampled", "blocked", "pending"))
    top = sorted(((n, name) for (name, _, _), (s, n, _) in
                  [((nm, c, r), status_of(nm)) for nm, c, r in CELLS] if n > 0),
                 reverse=True)[:8]
    bars = "".join(
        f'<div class="brow"><span class="bname">{n}</span>'
        f'<div class="btrack"><div class="bfill" style="width:{100 * v / top[0][0]:.0f}%"></div></div>'
        f'<span class="bval">{v}</span></div>' for v, n in top)
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>GST State Coverage Map</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.4rem;letter-spacing:-.4px}}.sub{{color:#555;font-size:.9rem}}
.map{{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;max-width:640px;margin:1.5rem 0}}
.st{{border:2px solid;border-radius:10px;padding:10px 4px;text-align:center}}
.st b{{display:block;font-size:.95rem}}.st span{{font-size:.72rem;color:#444}}
.lg{{font-size:.82rem;margin-right:12px;text-transform:capitalize}}
.lg i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px}}
.brow{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:.85rem}}
.bname{{width:110px;text-align:right}}.bval{{width:50px;font-variant-numeric:tabular-nums}}
.btrack{{flex:1;background:#f1f5f9;border-radius:5px;height:12px}}
.bfill{{height:12px;border-radius:5px;background:linear-gradient(90deg,#4355d8,#7b8cf0)}}
.cards{{display:flex;gap:.8rem;margin:1rem 0}}.card{{border:1px solid #e5e7eb;border-radius:8px;padding:.6rem 1rem}}
.card b{{font-size:1.25rem;display:block}}.card span{{font-size:.78rem;color:#555}}
.note{{font-size:.82rem;color:#555}}
</style></head><body>
<h1>GST legislation coverage across India</h1>
<p class="sub">Official state sources only (.gov.in / .nic.in) · every file keeps its publisher URL · $0 local stack</p>
<div class="cards"><div class="card"><b>{total:,}</b><span>state files held</span></div>
<div class="card"><b>15/16</b><span>states harvesting</span></div>
<div class="card"><b>1</b><span>blocked (Bihar)</span></div></div>
<div class="map">{cells}</div>
<div>{legend}</div>
<h2>Top states by files held</h2>
{bars}
<p class="note">Strong ≥ 400 files · growing ≥ 10 · sampled = PoC slice · pending = queued harvester.
Regenerate anytime: <code>python3 gst-aar/law/coverage_map.py</code></p>
</body></html>"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({total:,} files)")


if __name__ == "__main__":
    main()
