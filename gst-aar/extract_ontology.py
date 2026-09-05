#!/usr/bin/env python3
"""Two-pass ontology extraction over the AAR corpus.

Pass 1 (deterministic, instant): regex over brief + text for HSN/SAC codes,
GST rates, notification/section/rule citations, GSTINs, outcome keywords.
Pass 2 (LLM, incremental): sector tags + subject descriptions + per-question
holdings via LM Studio, JSON-only output. Resumable via rulings.ontology_extracted.

Usage:
  python3 extract_ontology.py --apply-pass1          # regex pass, all rulings
  python3 extract_ontology.py --llm --limit 5        # smoke-test LLM pass
  python3 extract_ontology.py --llm                  # full LLM pass (background)
"""
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "data" / "aar.db"
LMSTUDIO = "http://localhost:1234/v1/chat/completions"
LLM_MODEL = "ornith-1.5-35b-a3b"

# ---------------------------------------------------------------- regex pass
HSN_RE = re.compile(r"\bHSN(?:[/\s-]*SAC)?\s*(?:code)?\s*[:\-]?\s*([0-9]{4}(?:[0-9]{2,4})?)\b", re.I)
BARE_HSN_RE = re.compile(r"\b([0-9]{6}|[0-9]{8})\b(?=\s*(?:is|as|under|falls|classif))", re.I)
NOTIF_RE = re.compile(
    r"Notification(?:s)?\s+(?:No\.?\s*)?(\d{1,3}/20\d{2}(?:\s*[-–/]\s*(?:Central(?:\s+Tax)?(?:\s*\(Rate\))?|CT(?:\(R\))?|CGST|IGST|UTGST|Integrated\s+Tax|Compensation\s+Cess(?:\s*\(Rate\))?|Customs))?)",
    re.I,
)
SECTION_RE = re.compile(r"\b[Ss]ection[s]?\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))*)\s+(?:of\s+the\s+)?((?:CGST|SGST|IGST|UTGST|Integrated\s+Goods\s+and\s+Services\s+Tax|Central\s+Goods\s+and\s+Services\s+Tax)[A-Za-z\s,]*?Act)", re.I)
RULE_RE = re.compile(r"\bRule\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))*)\s+(?:of\s+the\s+)?([A-Z][A-Za-z\s,]{3,60}?Rules)", re.I)
RATE_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*%", re.I)
GSIN_RE = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b")
OUTCOME_PATTERNS = [
    ("withdrawn", re.compile(r"application withdrawn|applicant withdrew|withdraws its application", re.I)),
    ("rejected", re.compile(r"application (?:is|was|be) rejected|declined to (?:answer|rule)", re.I)),
    ("no_ruling", re.compile(r"no ruling (?:is|was) (?:given|issued)|not (?:a )?fit case|returns the application", re.I)),
    ("ruling_given", re.compile(r"(authority|we) (?:hereby )?(?:holds?|rules?|answer[sd]?)", re.I)),
]
SECTOR_KEYWORDS = {
    "education": ["educational institution", "education", "school", "college", "training", "coaching"],
    "construction": ["construction", "works contract", "civil construction", "builder", "flat", "real estate"],
    "it-services": ["software", "it services", "information technology", "saas", "cloud", "e-invoic", "platform"],
    "hospitality": ["restaurant", "hotel", "resort", "catering", "banquet"],
    "transport": ["transport", "logistics", "goods transport", "courier", "freight", "gtas"],
    "manufacturing": ["manufactur", "factory", "production of goods"],
    "healthcare": ["hospital", "clinic", "health care", "medical", "pharma"],
    "finance": ["banking", "loan", "nbfc", "insurance", "securit", "leasing"],
    "agriculture": ["agricultur", "farmer", "seed", "fertilizer", "crop"],
    "energy": ["electricity", "solar", "power", "renewable"],
    "media": ["cinema", "television", "broadcast", "advertis"],
}


def normalize_hsn(raw: str) -> str:
    return re.sub(r"\D", "", raw)


SUFFIX_MAP = [
    (r"CENTRALTAX\(RATE\)|CGST\(RATE\)|CT\(R\)", "CT(R)"),
    (r"INTEGRATEDTAX\(RATE\)|IGST\(RATE\)|IT\(R\)", "IGST(R)"),
    (r"UNIONTERRITORYTAX\(RATE\)|UTGST\(RATE\)|UTT\(R\)", "UTGST(R)"),
    (r"COMPENSATIONCESS\(RATE\)|CESS\(RATE\)", "CESS(R)"),
    (r"CENTRALTAX|CGST|CT", "CT"),
    (r"INTEGRATEDTAX|IGST", "IGST"),
    (r"UNIONTERRITORYTAX|UTGST|UTT", "UTGST"),
    (r"COMPENSATIONCESS|CESS", "CESS"),
    (r"CUSTOMS", "CUSTOMS"),
]


def norm_notification(raw: str) -> str:
    m = re.match(r"(\d{1,3})/(20\d{2})(?:\s*[-–/]\s*(.+))?", raw)
    if not m:
        return raw.replace(" ", "")
    no, yr, suffix = m.groups()
    s = re.sub(r"\s+", "", (suffix or "CT")).upper()
    for pat, canon in SUFFIX_MAP:
        if re.fullmatch(pat, s) or re.fullmatch(pat + r"[A-Z]*", s):
            return f"{no}/{yr}-{canon}"
    return f"{no}/{yr}-{s}"


def pass1(con: sqlite3.Connection):
    rulings = con.execute(
        "SELECT id, brief, COALESCE(txt_file,'') FROM rulings"
    ).fetchall()
    counts = {"hsn": 0, "notif": 0, "section": 0, "rule": 0, "gstin": 0, "outcome": 0, "tags": 0, "rates": 0}
    for rid, brief, txt_file in rulings:
        text = brief or ""
        p = ROOT / txt_file if txt_file else None
        body = p.read_text(errors="replace")[:20000] if p and p.exists() else ""
        full = text + "\n" + body[:12000]

        con.execute("DELETE FROM ruling_subjects WHERE ruling_id=? AND source='regex'", (rid,))
        con.execute("DELETE FROM ruling_citations WHERE ruling_id=? AND source='regex'", (rid,))

        # HSN codes (dedupe, keep raw form)
        seen = set()
        for m in HSN_RE.finditer(full):
            raw = m.group(1)
            norm = normalize_hsn(raw)
            if norm and norm not in seen:
                seen.add(norm)
                con.execute(
                    "INSERT INTO ruling_subjects (ruling_id, kind, description, hsn_sac, hsn_sac_raw, source)"
                    " VALUES (?, 'unspecified', NULL, ?, ?, 'regex')",
                    (rid, norm, raw),
                )
                counts["hsn"] += 1

        # notifications
        seen_n = set()
        for m in NOTIF_RE.finditer(full):
            ident = norm_notification(m.group(1))
            if ident not in seen_n:
                seen_n.add(ident)
                con.execute(
                    "INSERT INTO ruling_citations (ruling_id, kind, identifier, raw_text, source)"
                    " VALUES (?, 'notification', ?, ?, 'regex')",
                    (rid, ident, m.group(0)),
                )
                counts["notif"] += 1

        # sections
        seen_s = set()
        for m in SECTION_RE.finditer(full):
            ident = f"{('CGST' if 'central' in m.group(2).lower() else 'IGST' if 'integrated' in m.group(2).lower() else 'SGST')} s.{m.group(1)}"
            if ident not in seen_s:
                seen_s.add(ident)
                con.execute(
                    "INSERT INTO ruling_citations (ruling_id, kind, identifier, raw_text, source)"
                    " VALUES (?, 'section', ?, ?, 'regex')",
                    (rid, ident, m.group(0)),
                )
                counts["section"] += 1

        # rules
        for m in RULE_RE.finditer(full):
            ident = f"{m.group(2).strip()} r.{m.group(1)}"
            con.execute(
                "INSERT INTO ruling_citations (ruling_id, kind, identifier, raw_text, source)"
                " VALUES (?, 'rule', ?, ?, 'regex')",
                (rid, ident, m.group(0)),
            )
            counts["rule"] += 1

        # GSTIN (body text only)
        m = GSIN_RE.search(body)
        if m:
            con.execute("UPDATE rulings SET applicant_gstin=? WHERE id=?", (m.group(1), rid))
            counts["gstin"] += 1

        # outcome keywords (brief preferred, then body)
        outcome = None
        for name, pat in OUTCOME_PATTERNS:
            if pat.search(text) or (body and pat.search(body[:4000])):
                outcome = name
                break
        if outcome:
            con.execute("UPDATE rulings SET outcome=? WHERE id=? AND outcome IS NULL", (outcome, rid))
            counts["outcome"] += 1

        # sector tags
        low = (text + " " + body[:6000]).lower()
        for tag, kws in SECTOR_KEYWORDS.items():
            if any(k in low for k in kws):
                con.execute(
                    "INSERT OR IGNORE INTO ruling_tags (ruling_id, tag, source) VALUES (?, ?, 'brief')",
                    (rid, tag),
                )
                counts["tags"] += 1

    con.commit()
    print("pass1 done:", counts)


# ---------------------------------------------------------------- LLM pass
LLM_PROMPT = """You extract structured data from an Indian GST advance ruling. Return ONLY valid JSON (no markdown) with exactly these keys:
{
 "sector": ["one or two of: education, construction, it-services, hospitality, transport, manufacturing, healthcare, finance, agriculture, energy, media, retail, professional-services, other"],
 "applicant_type": "company|individual|partnership|trust|society|huf|government|null",
 "outcome": "ruling_given|withdrawn|rejected|no_ruling|null",
 "subject": {"kind": "good|service|both|null", "description": "<=25 words on what is supplied/asked about", "hsn_sac": "main code or null", "rate_proposed": "rate claimed or null", "rate_held": "rate determined or null"}
}
Null means unknown; do not guess."""


def llm_extract(con: sqlite3.Connection, rid: int, brief: str, text: str) -> bool:
    content = f"BRIEF: {brief[:1500]}\n\nTEXT (excerpt): {text[:4500]}"
    req = urllib.request.Request(
        LMSTUDIO,
        data=json.dumps({
            "model": LLM_MODEL,
            "temperature": 0,
            "max_tokens": 4000,  # thinking model burns reasoning tokens before output
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": LLM_PROMPT},
                {"role": "user", "content": content},
            ],
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            resp = json.loads(r.read())
        raw = resp["choices"][0]["message"]["content"]
        raw = re.sub(r"^```(json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
        d = json.loads(raw)
    except Exception as e:
        print(f"  ruling {rid}: LLM parse failed: {type(e).__name__}", file=sys.stderr)
        return False

    # normalize model verbosity into our vocab
    APPLICANT_MAP = {"private limited company": "company", "public limited company": "company",
                     "llp": "partnership", "partnership firm": "partnership",
                     "proprietorship": "individual", "sole proprietor": "individual"}
    at = (d.get("applicant_type") or "").strip().lower()
    at = next((v for k, v in APPLICANT_MAP.items() if k in at), at or None)

    s = d.get("subject") or {}
    if s.get("description"):
        con.execute(
            "INSERT INTO ruling_subjects (ruling_id, kind, description, hsn_sac, rate_proposed, rate_held, source)"
            " VALUES (?,?,?,?,?,?, 'llm')",
            (rid, s.get("kind"), s["description"],
             normalize_hsn(s["hsn_sac"]) if s.get("hsn_sac") else None,
             s.get("rate_proposed"), s.get("rate_held")),
        )
    for tag in (d.get("sector") or []):
        tag = re.sub(r"\s+", "-", str(tag).strip().lower())[:40]
        if tag and tag != "other":
            con.execute("INSERT OR IGNORE INTO ruling_tags (ruling_id, tag, source) VALUES (?, ?, 'llm')", (rid, tag))
    updates, vals = ["ontology_extracted=1"], []
    if at:
        updates.append("applicant_type=?"); vals.append(at)
    if d.get("outcome"):
        updates.append("outcome=COALESCE(outcome, ?)"); vals.append(d["outcome"])
    vals.append(rid)
    con.execute(f"UPDATE rulings SET {', '.join(updates)} WHERE id=?", vals)
    con.commit()
    return True


def pass2(con: sqlite3.Connection, limit=None):
    rows = con.execute(
        "SELECT id, brief, COALESCE(txt_file,'') FROM rulings WHERE ontology_extracted=0 ORDER BY id"
        + (f" LIMIT {limit}" if limit else "")
    ).fetchall()
    print(f"LLM pass: {len(rows)} rulings to extract")
    ok = 0
    t0 = time.time()
    for rid, brief, txt_file in rows:
        text = ""
        p = ROOT / txt_file if txt_file else None
        if p and p.exists():
            text = p.read_text(errors="replace")
        if llm_extract(con, rid, brief or "", text):
            ok += 1
        if ok % 25 == 0 and ok:
            print(f"[{ok}/{len(rows)}] {ok/(time.time()-t0):.2f} rulings/s", flush=True)
    print(f"LLM pass done: {ok}/{len(rows)} extracted in {(time.time()-t0)/60:.1f} min")


def main():
    con = sqlite3.connect(DB)
    con.executescript(Path(__file__).with_name("ontology.sql").read_text())
    # idempotent column adds (ontology.sql intentionally omits ALTERs)
    existing = {r[1] for r in con.execute("PRAGMA table_info(rulings)")}
    for col, typ in [("outcome", "TEXT"), ("applicant_gstin", "TEXT"),
                     ("applicant_type", "TEXT"), ("ontology_extracted", "INTEGER DEFAULT 0")]:
        if col not in existing:
            con.execute(f"ALTER TABLE rulings ADD COLUMN {col} {typ}")
    con.commit()
    if "--apply-pass1" in sys.argv:
        pass1(con)
    elif "--llm" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
        pass2(con, limit)
    con.close()


if __name__ == "__main__":
    main()
