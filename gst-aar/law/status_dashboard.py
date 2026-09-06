#!/usr/bin/env python3
"""Regenerable visual scraping-status dashboard.

Queries aar.db + law.db + the filesystem and emits a self-contained HTML
page: what is downloaded, the universe of GST documents, what is missing,
and the embeddings/serving setup.

Usage: python3 status_dashboard.py   (writes gst-aar/status.html)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "status.html"


def q(db: Path, sql: str, args: tuple = ()):
    try:
        con = sqlite3.connect(db)
        return con.execute(sql, args).fetchall()
    except Exception:
        return []


def build() -> str:
    aar = ROOT / "data" / "aar.db"
    law = ROOT / "data" / "law" / "law.db"

    rulings = q(aar, "SELECT COUNT(*) FROM rulings")[0][0]
    with_text = q(aar, "SELECT COUNT(*) FROM rulings WHERE txt_file IS NOT NULL")[0][0]
    chunks = q(aar, "SELECT COUNT(*) FROM chunks")[0][0]
    null_emb = q(aar, "SELECT COUNT(*) FROM chunks WHERE embedding IS NULL")[0][0]
    ext = q(aar, "SELECT extraction_status, COUNT(*) FROM rulings GROUP BY 1")
    onto = {}
    for t in ("ruling_subjects", "ruling_citations", "ruling_tags", "ruling_questions"):
        r = q(aar, f"SELECT COUNT(*) FROM {t}")
        onto[t] = r[0][0] if r else 0

    law_docs = q(law, "SELECT kind, COUNT(*), MIN(pub_date), MAX(pub_date) FROM documents GROUP BY 1")
    law_chunks = q(law, "SELECT COUNT(*) FROM law_chunks")[0][0]
    law_onto = {}
    for t in ("law_subjects", "law_citations", "law_tags"):
        r = q(law, f"SELECT COUNT(*) FROM {t}")
        law_onto[t] = r[0][0] if r else 0

    pdfs = sum(1 for _ in (ROOT / "data" / "pdfs").rglob("*.pdf")) if (ROOT / "data" / "pdfs").exists() else 0
    texts = sum(1 for _ in (ROOT / "data" / "text").rglob("*.txt")) if (ROOT / "data" / "text").exists() else 0
    law_pdfs = sum(1 for _ in (ROOT / "data" / "law").rglob("*.pdf"))
    law_texts = sum(1 for _ in (ROOT / "data" / "law" / "text").rglob("*.txt"))

    def du(p: Path) -> str:
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
        return f"{total / 1e9:.1f} GB"

    universe = [
        ("AAR / AAAR rulings", "~2,900", f"{rulings:,}", "done", "gstcouncil.gov.in"),
        ("Central GST Bills (as introduced)", "5", "5", "done", "cbic-gst.gov.in"),
        ("Central Acts (section text)", "5 + amendments", "5 meta", "partial", "taxinformation.cbic.gov.in"),
        ("Notifications 2017→2026", "low 1,000s (est.)", "10", "missing", "cbic-gst.gov.in"),
        ("Circulars / instructions", "200+ (est.)", "0", "missing", "cbic-gst.gov.in"),
        ("HSN/SAC rate master", "~5,200 codes (est.)", "tags only", "missing", "derived"),
        ("CGST Rules + Forms + GSTAT Rules", "~160 + 124", "1 sample", "missing", "taxinformation.cbic.gov.in"),
        ("SGST Acts (states)", "~31 (est.)", "0", "missing", "indiacode.gov.in"),
        ("State SGST Bills", "~31, uneven (est.)", "0", "missing", "state legislatures"),
        ("GSTAT orders (live since Feb 2026)", "growing daily", "4 notices", "blocked", "gstat.gov.in (CAPTCHA)"),
        ("SC GST judgments (eSCR)", "27 found", "3", "paused", "scr.sci.gov.in (CAPTCHA)"),
        ("HC GST judgments (eSCR)", "unknown", "0", "missing", "judgments.ecourts.gov.in"),
        ("Council recommendations", "50+ meetings (est.)", "0", "missing", "gstcouncil.gov.in"),
        ("Debates + Select Committee report", "handful", "0", "missing", "loksabha.nic.in"),
        ("CESTAT (adjacent)", "large", "0", "low-pri", "cestat.gov.in"),
    ]

    def bar(status: str) -> str:
        color = {"done": "#16a34a", "partial": "#d97706", "missing": "#dc2626",
                 "blocked": "#7c3aed", "paused": "#d97706", "low-pri": "#6b7280"}[status]
        width = {"done": 100, "partial": 45, "missing": 4, "blocked": 15,
                 "paused": 25, "low-pri": 4}[status]
        label = {"done": "done", "partial": "partial", "missing": "missing",
                 "blocked": "blocked", "paused": "paused", "low-pri": "low priority"}[status]
        return (f'<div class="bar"><div class="fill" style="width:{width}%;'
                f'background:{color}"></div></div><span class="st">{label}</span>')

    rows = "\n".join(
        f"<tr><td>{a}</td><td class=num>{b}</td><td class=num>{c}</td>"
        f"<td>{bar(d)}</td><td class=src>{e}</td></tr>"
        for a, b, c, d, e in universe)

    law_rows = "\n".join(
        f"<tr><td>{k}</td><td class=num>{n}</td><td class=num>{mn or '—'} → {mx or '—'}</td></tr>"
        for k, n, mn, mx in law_docs)
    ext_rows = "\n".join(
        f"<tr><td>{s}</td><td class=num>{n:,}</td></tr>" for s, n in ext)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>GST Corpus — Scraping Status</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.5rem}}h2{{font-size:1.15rem;margin-top:2rem;border-bottom:2px solid #eee;padding-bottom:.3rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
td,th{{border:1px solid #e5e7eb;padding:.45rem .6rem;text-align:left}}
th{{background:#f8fafc}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.src{{color:#555;font-size:.82rem}}
.bar{{width:120px;height:10px;background:#f1f5f9;border-radius:5px;display:inline-block;vertical-align:middle}}
.fill{{height:10px;border-radius:5px}}.st{{font-size:.8rem;margin-left:.4rem;text-transform:capitalize}}
.cards{{display:flex;gap:.8rem;flex-wrap:wrap}}.card{{border:1px solid #e5e7eb;border-radius:8px;padding:.7rem 1rem;min-width:140px}}
.card b{{font-size:1.3rem;display:block}}.card span{{font-size:.8rem;color:#555}}
.meta{{color:#555;font-size:.85rem}}
</style></head><body>
<h1>GST Corpus — Scraping Status</h1>
<p class="meta">Generated locally · official sources only (.gov.in / .nic.in) · $0 stack (SQLite + LM Studio + Vision OCR)</p>

<h2>At a glance</h2>
<div class="cards">
<div class="card"><b>{rulings:,}</b><span>AAR rulings</span></div>
<div class="card"><b>{with_text:,}</b><span>with text ({with_text / rulings:.0%})</span></div>
<div class="card"><b>{chunks:,}</b><span>AAR embeddings ({null_emb} null)</span></div>
<div class="card"><b>{sum(n for _, n, _, _ in law_docs)}</b><span>law documents</span></div>
<div class="card"><b>{law_chunks:,}</b><span>law embeddings</span></div>
<div class="card"><b>{pdfs + law_pdfs:,}</b><span>PDFs ({du(ROOT / 'data' / 'pdfs')} + {du(ROOT / 'data' / 'law')})</span></div>
</div>

<h2>Universe vs held</h2>
<table><tr><th>Layer</th><th>Universe</th><th>Held</th><th>Status</th><th>Source</th></tr>
{rows}</table>

<h2>Law documents by kind (law.db)</h2>
<table><tr><th>Kind</th><th>Count</th><th>Date range</th></tr>{law_rows}</table>

<h2>AAR extraction funnel</h2>
<table><tr><th>Status</th><th>Count</th></tr>{ext_rows}</table>
<p class="meta">Texts: {texts:,} · Law texts: {law_texts:,}</p>

<h2>Ontology (structured layer)</h2>
<table><tr><th>Table</th><th>Rows</th></tr>
<tr><td>ruling_subjects / citations / tags / questions</td><td class=num>{onto['ruling_subjects']:,} / {onto['ruling_citations']:,} / {onto['ruling_tags']:,} / {onto['ruling_questions']:,}</td></tr>
<tr><td>law_subjects / citations / tags</td><td class=num>{law_onto['law_subjects']:,} / {law_onto['law_citations']:,} / {law_onto['law_tags']:,}</td></tr>
</table>

<h2>Embeddings &amp; serving</h2>
<table><tr><th>Component</th><th>Detail</th></tr>
<tr><td>Embedding model</td><td>text-embedding-nomic-embed-text-v1.5, 768-d, via LM Studio :1234</td></tr>
<tr><td>LLM (chat + ontology)</td><td>ornith-1.5-35b-a3b, via LM Studio :1234</td></tr>
<tr><td>Search</td><td>SQLite FTS5 BM25 + cosine over chunks; recency precedence (rank, pub_date DESC)</td></tr>
<tr><td>Webapp :3210</td><td>/api/search, /api/semantic, /api/chat, /api/document, /api/law, /api/changes</td></tr>
<tr><td>Freshness</td><td>check_daily.py (dry-run) — pulls paused eSCR/GSTAT need assisted CAPTCHA sessions</td></tr>
</table>
</body></html>"""
    return html


def main() -> None:
    html = build()
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html) // 1024}KB)")


if __name__ == "__main__":
    main()
