#!/usr/bin/env python3
"""Build the local searchable SQLite database of AAR/AAAR rulings.

- `rulings` table: metadata from the GST Council listing + file paths + text stats
- `rulings_fts`: FTS5 full-text index over the full order text + metadata

Usage: python3 build_db.py   (rebuilds data/aar.db from jsonl + text files)
"""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "aar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rulings (
    id INTEGER PRIMARY KEY,
    sr_no TEXT,
    applicant TEXT,
    state TEXT,
    brief TEXT,
    order_no_date TEXT,
    order_no TEXT,
    order_date TEXT,
    category TEXT,
    pdf_url TEXT,
    pdf_path TEXT,
    pdf_file TEXT,
    txt_file TEXT,
    pages INTEGER,
    chars INTEGER,
    extraction_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_rulings_state ON rulings(state);
CREATE INDEX IF NOT EXISTS idx_rulings_date ON rulings(order_date);
CREATE INDEX IF NOT EXISTS idx_rulings_applicant ON rulings(applicant);

CREATE VIRTUAL TABLE IF NOT EXISTS rulings_fts USING fts5(
    applicant, brief, order_no_date, category, body,
    tokenize='porter unicode61'
);
"""

DATE_PATTERNS = [
    r"[Dd]ated\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})",
]
ORDER_NO_RE = re.compile(r"([A-Z]{2,4}[.\s/]*(?:AAR|AAAR|ADRG|APPEL?LANT?)[^,;]*?)(?:\s*,\s*dated|$)", re.I)


def split_order_field(s: str) -> tuple[str, str]:
    """Split 'ORDER NO ..., dated DD.MM.YYYY' into (no, ISO date)."""
    no, date = s.strip(), ""
    m = None
    for pat in DATE_PATTERNS:
        m = re.search(pat, s)
        if m:
            break
    if m:
        raw = m.group(1)
        parts = re.split(r"[./-]", raw)
        try:
            dd, mm, yy = parts[0], parts[1], parts[2]
            yy = "20" + yy if len(yy) == 2 else yy
            date = f"{yy}-{int(mm):02d}-{int(dd):02d}"
        except (ValueError, IndexError):
            date = raw
        no = s[: m.start()].rstrip(" ,;:").strip()
    return no, date


def find_text_file(pdf_rel: str | None) -> str | None:
    if not pdf_rel:
        return None
    cand = DATA / "text" / Path(pdf_rel).with_suffix(".txt")
    return str(cand.relative_to(ROOT)) if cand.exists() else None


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    for old in (DB, Path(str(DB) + "-wal"), Path(str(DB) + "-shm")):
        if old.exists():
            old.unlink()

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    # load listing
    records = {}
    with (DATA / "aar_list.jsonl").open() as f:
        for line in f:
            r = json.loads(line)
            if r.get("pdf_url"):
                records[r["pdf_url"]] = r

    # load extraction status
    text_status = {}
    if (DATA / "extract_status.jsonl").exists():
        with (DATA / "extract_status.jsonl").open() as f:
            for line in f:
                st = json.loads(line)
                text_status[st["pdf"]] = st

    def status_for(url: str, state: str) -> dict:
        """Map a listing record onto extract_status via its local path key."""
        name = url.rsplit("/", 1)[-1]
        state_dir = (state or "unknown").strip().replace(" ", "_").replace("/", "-")
        return text_status.get(f"{state_dir}/{name}", {})

    rows = []
    for url, r in records.items():
        name = url.rsplit("/", 1)[-1]
        state_dir = (r.get("state") or "unknown").strip().replace(" ", "_").replace("/", "-")
        pdf_file = DATA / "pdfs" / state_dir / name
        pdf_file = str(pdf_file) if pdf_file.exists() else None
        st = status_for(url, r.get("state"))
        txt_file = None
        if st.get("status") in ("ok", "cached"):
            cand = DATA / "text" / state_dir / (name.rsplit(".", 1)[0] + ".txt")
            txt_file = str(cand.relative_to(ROOT)) if cand.exists() else None
        order_no, order_date = split_order_field(r.get("order_no_date", ""))
        body = ""
        if txt_file:
            body = (ROOT / txt_file).read_text(encoding="utf-8", errors="replace")
        rows.append((
            r.get("sr_no"), r.get("applicant"), r.get("state"), r.get("brief"),
            r.get("order_no_date"), order_no, order_date, r.get("category"),
            url, r.get("pdf_path"), pdf_file, txt_file,
            st.get("pages"), st.get("chars"), st.get("status", "not_downloaded"),
        ))

    con.executemany(
        "INSERT INTO rulings (sr_no, applicant, state, brief, order_no_date, order_no,"
        " order_date, category, pdf_url, pdf_path, pdf_file, txt_file, pages, chars,"
        " extraction_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()

    print(f"metadata rows: {len(rows)}")
    print("populating FTS with metadata + body text...")
    con.execute(
        "INSERT INTO rulings_fts(rowid, applicant, brief, order_no_date, category, body) "
        "SELECT id, applicant, brief, order_no_date, category, '' FROM rulings"
    )
    cur = con.execute("SELECT id, txt_file FROM rulings WHERE txt_file IS NOT NULL")
    for rid, txt_file in cur:
        body = (ROOT / txt_file).read_text(encoding="utf-8", errors="replace")
        con.execute("UPDATE rulings_fts SET body = ? WHERE rowid = ?", (body, rid))
    con.commit()

    counts = con.execute(
        "SELECT extraction_status, COUNT(*) FROM rulings GROUP BY 1"
    ).fetchall()
    print("extraction status:", counts)
    n_fts = con.execute("SELECT COUNT(*) FROM rulings_fts").fetchone()[0]
    print(f"FTS rows: {n_fts}")
    con.close()
    print(f"DB built: {DB}")


if __name__ == "__main__":
    main()
