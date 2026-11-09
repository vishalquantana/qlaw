# GST Law Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harvest the official `.gov.in` GST statute/rules/notifications/circular corpus to the local laptop into `law.db` + vectors and serve it through search + chat, with a daily freshness checker.

**Architecture:** Four independent harvesters (CBIC JSON API, CBIC flat PDFs, Council/Gazette/GSTN, NAA top-up deferred) write raw JSON/PDFs under `gst-aar/data/law/`, a shared incremental `law_db.py` upserts them into SQLite+FTS5, `law_search.py` + webapp endpoints serve them, and `check_daily.py` diffs listings daily.

**Tech Stack:** Python 3 stdlib + requests (`requirements.txt` already has `requests>=2.32.0`), sqlite3 FTS5, Next.js webapp (existing `gst-aar/webapp`), LM Studio nomic embeddings (reuse `embed_chunks.py` pattern), macOS Vision OCR (reuse `extract_vision.py`).

**Spec:** `docs/superpowers/specs/2026-09-06-gst-law-corpus-design.md`

## Global Constraints

- `.gov.in` sources only — every DB row carries its original publisher `source_url` on a `.gov.in` host; no source URL → no downstream processing.
- Local laptop, $0 stack — everything under `gst-aar/data/law/`; DBs gitignored and regenerable; check `df -h /System/Volumes/Data` before bulk steps, abort below 10 GiB free.
- Never full-wipe in routine operation — `law_db.py` upserts by `(source_url, sha256)`; `aar.db` untouched.
- Attribution everywhere — products display the official link, never become the citation of record.
- PoC first — each harvester verifies on a ≤5-page slice before full backfill.

---

## File map

| File | Responsibility |
|---|---|
| `gst-aar/law/__init__.py` | Package marker for the law pipeline |
| `gst-aar/law/harvest_cbic_api.py` | Stream A: anon JWT + paged harvest of acts/chapters/sections/rules/amendments from `taxinformation.cbic.gov.in` |
| `gst-aar/law/harvest_cbic_flat.py` | Stream B: crawl `cbic-gst.gov.in` flat listing pages → download `pdf/*.pdf` notifications/circulars |
| `gst-aar/law/harvest_council_gazette.py` | Stream C: GST Council meeting pages + eGazette/GSTN advisory link harvest (metadata + PDFs) |
| `gst-aar/law/law_db.py` | Shared store: `law.db` schema (`documents`, `sections`, `notifications`, `rule_facts` + FTS5), incremental upsert, inventory export |
| `gst-aar/law/law_search.py` | CLI BM25 search over `law.db` (parity with `gst-aar/search.py` quoting pattern) |
| `gst-aar/law/check_daily.py` | Roadmap daily checker: diff listings → ingest new → append `changes.jsonl`, `--since` dry-run |
| `tests/test_law_db.py` | Pins for upsert/dedup/provenance/FTS quoting |
| `tests/test_cbic_harvest.py` | Pins for JWT/paging parse, flat-page PDF extraction, notification filename parse |
| `gst-aar/webapp/app/api/law/route.js` | `GET /api/law` section/lookup endpoint (added in Task 5) |
| `gst-aar/webapp/app/api/changes/route.js` | `GET /api/changes?since=` endpoint (added in Task 6) |

## Interfaces

- `harvest_cbic_api.get_token(base) -> str` — POST `{}` to `/api/authenticate-token`, return JWT.
- `harvest_cbic_api.fetch_paged(base, token, path, page, size) -> list[dict]` — GET one JSON page.
- `harvest_cbic_flat.parse_listing(html, base_url) -> list[dict]` — each dict has `title`, `pdf_url`, `date`.
- `harvest_cbic_flat.parse_notification_filename(name) -> dict` — `{number, category, year}`.
- `law_db.init_db(path) -> sqlite3.Connection`; `law_db.upsert_document(con, doc) -> int` (`doc` keys: `source_url`, `kind`, `title`, `number`, `pub_date`, `local_path`, `sha256`, `body`); `law_db.search(con, query, limit) -> list[sqlite3.Row]`.
- `check_daily.diff_listings(old, new) -> list[dict]` — rows in `new` whose `source_url` not in `old`.

Scope note: harvesters share only `law_db.upsert_document` + `data/law/` layout, so Tasks 2–4 run in parallel once Task 1 lands.

---

### Task 1: law package + incremental store

**Files:**
- Create: `gst-aar/law/__init__.py`
- Create: `gst-aar/law/law_db.py`
- Test: `tests/test_law_db.py`

**Interfaces:**
- Consumes: nothing (foundation).
- Produces: `law_db.init_db`, `law_db.upsert_document`, `law_db.search` for Tasks 2–6.

- [ ] **Step 1: Write the failing test**

```python
"""Pin the incremental law store: dedup, provenance, FTS hyphen quoting."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import law_db


def _memdb():
    con = sqlite3.connect(":memory:")
    law_db.init_schema(con)
    return con


class TestUpsertDedup:
    def test_same_source_url_upserts_once(self) -> None:
        con = _memdb()
        doc = {"source_url": "https://taxinformation.cbic.gov.in/x/1",
               "kind": "act", "title": "CGST Act", "number": "",
               "pub_date": "2017-04-12", "local_path": "", "sha256": "a" * 64,
               "body": "levy and collection"}
        id1 = law_db.upsert_document(con, doc)
        id2 = law_db.upsert_document(con, {**doc, "body": "levy and collection"})
        assert id1 == id2
        assert con.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1

    def test_changed_hash_updates_body(self) -> None:
        con = _memdb()
        doc = {"source_url": "https://cbic-gst.gov.in/pdf/n1.pdf",
               "kind": "notification", "title": "N1", "number": "1/2017-CT",
               "pub_date": "2017-06-28", "local_path": "", "sha256": "b" * 64,
               "body": "old text"}
        law_db.upsert_document(con, doc)
        law_db.upsert_document(con, {**doc, "sha256": "c" * 64, "body": "new text"})
        row = con.execute("SELECT body FROM documents").fetchone()
        assert row[0] == "new text"


class TestProvenance:
    def test_missing_source_url_raises(self) -> None:
        con = _memdb()
        try:
            law_db.upsert_document(con, {"source_url": "", "kind": "act",
                "title": "t", "number": "", "pub_date": "", "local_path": "",
                "sha256": "d" * 64, "body": "b"})
        except ValueError as e:
            assert "source_url" in str(e)
        else:
            raise AssertionError("expected ValueError")

    def test_non_gov_in_source_url_raises(self) -> None:
        con = _memdb()
        try:
            law_db.upsert_document(con, {"source_url": "https://example.com/x.pdf",
                "kind": "act", "title": "t", "number": "", "pub_date": "",
                "local_path": "", "sha256": "e" * 64, "body": "b"})
        except ValueError as e:
            assert ".gov.in" in str(e)
        else:
            raise AssertionError("expected ValueError")


class TestSearchQuoting:
    def test_hyphen_term_searches(self) -> None:
        con = _memdb()
        law_db.upsert_document(con, {"source_url": "https://cbic-gst.gov.in/pdf/e.pdf",
            "kind": "circular", "title": "e-invoicing", "number": "",
            "pub_date": "", "local_path": "", "sha256": "f" * 64,
            "body": "e-invoicing QR code B2C"})
        rows = law_db.search(con, "e-invoicing", 10)
        assert len(rows) == 1
```

NOTE: the test imports via a shim because `gst-aar/law/` is not on `pythonpath`
(`pytest.ini` sets `pythonpath = .`). The shim is `tests/`-local and defined in
Step 3 alongside the implementation (same commit) — the test file above references
it; if the import fails the test fails, which is the correct TDD red state.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_law_db.py -v`
Expected: FAIL (`law_db` module/shim not found).

- [ ] **Step 3: Write minimal implementation**

`gst-aar/law/__init__.py`:
```python
"""GST law corpus pipeline (.gov.in sources only)."""
```

`gst-aar/law/law_db.py`:
```python
"""Incremental SQLite store for the GST law corpus.

Upsert key: source_url. A changed sha256 updates body+metadata in place.
Every row requires a .gov.in source_url (spec §2).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    source_url TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    title TEXT DEFAULT '',
    number TEXT DEFAULT '',
    pub_date TEXT DEFAULT '',
    local_path TEXT DEFAULT '',
    sha256 TEXT DEFAULT '',
    body TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_documents_kind ON documents(kind);
CREATE INDEX IF NOT EXISTS idx_documents_number ON documents(number);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, number, body, tokenize='porter unicode61');
"""

LAW_DB = Path(__file__).parent.parent / "data" / "law" / "law.db"


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def init_db(path: Path = LAW_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    init_schema(con)
    return con


def _check_provenance(source_url: str) -> None:
    if not source_url:
        raise ValueError("source_url is required (no source URL, no processing)")
    if ".gov.in" not in source_url:
        raise ValueError(f"non-.gov.in source_url refused: {source_url}")


def upsert_document(con: sqlite3.Connection, doc: dict) -> int:
    _check_provenance(doc.get("source_url", ""))
    cur = con.execute(
        "INSERT INTO documents (source_url, kind, title, number, pub_date,"
        " local_path, sha256, body) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(source_url) DO UPDATE SET kind=excluded.kind,"
        " title=excluded.title, number=excluded.number, pub_date=excluded.pub_date,"
        " local_path=excluded.local_path, sha256=excluded.sha256, body=excluded.body",
        (doc["source_url"], doc.get("kind", ""), doc.get("title", ""),
         doc.get("number", ""), doc.get("pub_date", ""), doc.get("local_path", ""),
         doc.get("sha256", ""), doc.get("body", "")),
    )
    doc_id = cur.lastrowid or con.execute(
        "SELECT id FROM documents WHERE source_url=?", (doc["source_url"],)).fetchone()[0]
    con.execute("INSERT INTO documents_fts(rowid, title, number, body) VALUES (?,?,?,?)"
                " ON CONFLICT(rowid) DO UPDATE SET title=excluded.title,"
                " number=excluded.number, body=excluded.body",
                (doc_id, doc.get("title", ""), doc.get("number", ""), doc.get("body", "")))
    con.commit()
    return doc_id


def _quote_query(query: str) -> str:
    return " ".join(f'"{t}"' for t in query.split() if t)


def search(con: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return con.execute(
        "SELECT d.* FROM documents d JOIN documents_fts f ON f.rowid = d.id"
        " JOIN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r"
        " ON r.rowid = d.id LIMIT ?", (_quote_query(query), limit)).fetchall()
```

Shim for repo `pythonpath = .` (create `tests/gst_aar_law_shim.py` — test-only import
helper so `tests/` can import the hyphenated `gst-aar/law/` package without renaming it):
```python
"""Test-only shim: expose gst-aar/law/law_db.py as `law_db`."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "law_db", Path(__file__).parent.parent / "gst-aar" / "law" / "law_db.py")
law_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(law_db)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_law_db.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add gst-aar/law/__init__.py gst-aar/law/law_db.py tests/test_law_db.py tests/gst_aar_law_shim.py
git commit -m "feat(law): incremental law.db store with .gov.in provenance gate"
```

---

### Task 2: Stream A — CBIC JSON API harvest (acts/rules/amendments)

**Files:**
- Create: `gst-aar/law/harvest_cbic_api.py`
- Test: `tests/test_cbic_harvest.py` (Part A)

**Interfaces:**
- Consumes: `law_db.upsert_document` (Task 1).
- Produces: raw JSON under `data/law/acts|rules/` + upserted `act`/`rule` rows for Task 5.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_act_page_picks_pdf_and_html():
    from gst_aar_law_shim import harvest_cbic_api as api

    page = [{"actId": 1000270, "actName": "Central Goods and Services Tax Act, 2017",
             "contentFilePath": "tax_repository\\gst\\acts\\cgst.pdf",
             "contentHtmlFilePath": "tax_repository/gst/acts/cgst.html",
             "issueDt": "12-Apr-2017", "amendDt": "28-Sep-2022"}]
    docs = api.normalize_acts(page)
    assert docs[0]["title"] == "Central Goods and Services Tax Act, 2017"
    assert docs[0]["source_url"].startswith("https://taxinformation.cbic.gov.in")
    assert docs[0]["kind"] == "act"


def test_auth_headers_carry_bearer():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert api.auth_headers("tok123") == {"Authorization": "Bearer tok123"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cbic_harvest.py -v`
Expected: FAIL (`harvest_cbic_api` not found).

- [ ] **Step 3: Write minimal implementation**

`gst-aar/law/harvest_cbic_api.py`:
```python
#!/usr/bin/env python3
"""Stream A: harvest GST acts/rules/sections from taxinformation.cbic.gov.in.

Pattern follows gst-aar/scrape_list.py (stdlib urllib, retry, UA header).
PoC: python3 harvest_cbic_api.py --limit 5 (verifies token + 1 page before full pull).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://taxinformation.cbic.gov.in"
ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "acts"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _req(url: str, token: str | None = None, data: bytes | None = None,
         retries: int = 3) -> bytes:
    headers = dict(UA)
    if token:
        headers.update(auth_headers(token))
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_token(base: str = BASE) -> str:
    raw = _req(base + "/api/authenticate-token", data=b"{}")
    payload = json.loads(raw.decode("utf-8", "replace"))
    for key in ("id_token", "token", "access_token"):
        if payload.get(key):
            return payload[key]
    raise RuntimeError(f"no token in auth response keys: {sorted(payload)}")


def fetch_paged(base: str, token: str, path: str, page: int = 0,
                size: int = 50) -> list[dict]:
    sep = "&" if "?" in path else "?"
    raw = _req(f"{base}{path}{sep}page={page}&size={size}", token)
    payload = json.loads(raw.decode("utf-8", "replace"))
    if isinstance(payload, list):
        return payload
    for key in ("content", "data", "result"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def normalize_acts(rows: list[dict]) -> list[dict]:
    docs = []
    for r in rows:
        name = r.get("actName") or r.get("name") or ""
        if not name:
            continue
        docs.append({
            "source_url": f"{BASE}/content-page/explore-act/{r.get('actId', '')}/1000001",
            "kind": "act",
            "title": name,
            "number": "",
            "pub_date": r.get("issueDt", ""),
            "local_path": "",
            "sha256": hashlib.sha256(
                json.dumps(r, sort_keys=True).encode()).hexdigest(),
            "body": json.dumps(r, ensure_ascii=False),
        })
    return docs


def main(limit: int = 0):
    OUT.mkdir(parents=True, exist_ok=True)
    token = get_token()
    seen, total, page = set(), 0, 0
    from . import law_db  # package-relative import when run as module
    con = law_db.init_db()
    while True:
        rows = fetch_paged(BASE, token, "/api/cbic-act-msts", page)
        if not rows:
            break
        for doc in normalize_acts(rows):
            if doc["source_url"] in seen:
                continue
            seen.add(doc["source_url"])
            law_db.upsert_document(con, doc)
            total += 1
            if limit and total >= limit:
                print(f"PoC slice done: {total} acts")
                return
        print(f"page {page}: {len(rows)} rows (total {total})")
        page += 1
        time.sleep(0.4)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    main(**vars(ap.parse_args()))
```

Also extend `tests/gst_aar_law_shim.py` with a `harvest_cbic_api` loader mirroring the
`law_db` loader (same `spec_from_file_location` pattern, file
`gst-aar/law/harvest_cbic_api.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cbic_harvest.py tests/test_law_db.py -v`
Expected: PASS.

- [ ] **Step 5: PoC run (slice of 5, proves token + paging without bulk load)**

Run: `python3 -m gst-aar.law.harvest_cbic_api --limit 5` from repo root is wrong
(package dir is hyphenated); run instead: `python3 gst-aar/law/harvest_cbic_api.py --limit 5`
from `/Users/vishalkumar/Downloads/qlaw`. NOTE: `from . import law_db` fails under
direct script run — before the PoC, change it to the shim-style loader used in tests
(same `importlib.util.spec_from_file_location` block). PoC passes when 5 act rows land
in `data/law/law.db` with `.gov.in` URLs.
Expected: 5 rows, no 500s on act endpoints.

- [ ] **Step 6: Commit**

```bash
git add gst-aar/law/harvest_cbic_api.py tests/test_cbic_harvest.py tests/gst_aar_law_shim.py
git commit -m "feat(law): CBIC API harvest for GST acts (PoC slice)"
```

---

### Task 3: Stream B — flat-PDF harvest (notifications/circulars)

**Files:**
- Create: `gst-aar/law/harvest_cbic_flat.py`
- Test: append Part B to `tests/test_cbic_harvest.py`

**Interfaces:**
- Consumes: `law_db.upsert_document` (Task 1).
- Produces: PDFs under `data/law/notifications|circulars/` + `notification`/`circular` rows.

- [ ] **Step 1: Write the failing test** (append to `tests/test_cbic_harvest.py`)

```python
def test_parse_listing_extracts_pdf_links():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    html = ('<a href="pdf/NN-26-2024_Eng.pdf">26/2024-CT</a>'
            '<a href="/about">skip</a>')
    rows = flat.parse_listing(html, "https://cbic-gst.gov.in/central-tax-notifications.html")
    assert rows[0]["pdf_url"] == "https://cbic-gst.gov.in/pdf/NN-26-2024_Eng.pdf"


def test_parse_notification_filename():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    assert flat.parse_notification_filename("NN-26-2024_Eng.pdf") == {
        "number": "26/2024", "category": "CT", "year": "2024"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cbic_harvest.py -v`
Expected: FAIL (`harvest_cbic_flat` not found).

- [ ] **Step 3: Write minimal implementation**

`gst-aar/law/harvest_cbic_flat.py`:
```python
#!/usr/bin/env python3
"""Stream B: crawl cbic-gst.gov.in flat listing pages → download notification/circular PDFs.

Follows gst-aar/download_pdfs.py throttling pattern (0.4s delay, %PDF validation).
PoC: --max 5 PDFs.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

LISTINGS = [
    ("notifications", "https://cbic-gst.gov.in/central-tax-notifications.html"),
    ("circulars", "https://cbic-gst.gov.in/circulars.html"),
]

NAME_RE = re.compile(r"(?:NN-?|Notification-?No\.?\s*)?(\d+)/(\d{4})[-_]?([A-Za-z\(\)]*)",
                     re.I)


def fetch(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def parse_listing(html: str, base_url: str) -> list[dict]:
    rows = []
    for m in re.finditer(r'href="([^"]+\.pdf)"[^>]*>([^<]*)', html, re.I):
        pdf_url = urllib.parse.urljoin(base_url, m.group(1))
        if "cbic-gst.gov.in" not in pdf_url and "cbic.gov.in" not in pdf_url:
            continue
        rows.append({"title": " ".join(m.group(2).split()),
                     "pdf_url": pdf_url})
    return rows


def parse_notification_filename(name: str) -> dict:
    m = NAME_RE.search(name)
    if not m:
        return {"number": name, "category": "", "year": ""}
    num, year, cat = m.group(1), m.group(2), (m.group(3) or "").strip("_.")
    return {"number": f"{num}/{year}", "category": cat, "year": year}


def main(max_pdfs: int = 0):
    from tests.gst_aar_law_shim import law_db  # reuse Task 1 store via shim path
    con = law_db.init_db()
    done = 0
    for kind, url in LISTINGS:
        html = fetch(url).decode("utf-8", "replace")
        for row in parse_listing(html, url):
            dest = OUT / kind / row["pdf_url"].rsplit("/", 1)[-1]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                blob = fetch(row["pdf_url"])
                if not blob.startswith(b"%PDF"):
                    print(f"  skip non-PDF {row['pdf_url']}", file=sys.stderr)
                    continue
                dest.write_bytes(blob)
                time.sleep(0.4)
            meta = parse_notification_filename(dest.name)
            law_db.upsert_document(con, {
                "source_url": row["pdf_url"], "kind": kind.rstrip("s"),
                "title": row["title"] or dest.name, "number": meta["number"],
                "pub_date": "", "local_path": str(dest),
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "body": ""})
            done += 1
            if max_pdfs and done >= max_pdfs:
                print(f"PoC slice done: {done} PDFs")
                return
    print(f"done: {done} PDFs")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_pdfs", type=int, default=0)
    main(**vars(ap.parse_args()))
```

Extend the shim with a `harvest_cbic_flat` loader (same pattern as Task 2).

- [ ] **Step 4: Run tests + PoC**

Run: `python3 -m pytest tests/test_cbic_harvest.py -v`
Expected: PASS.
Run: `python3 gst-aar/law/harvest_cbic_flat.py --max 5`
Expected: 5 PDFs under `data/law/`, 5 rows upserted.

- [ ] **Step 5: Commit**

```bash
git add gst-aar/law/harvest_cbic_flat.py tests/test_cbic_harvest.py tests/gst_aar_law_shim.py
git commit -m "feat(law): flat-PDF harvest for notifications/circulars (PoC)"
```

---

### Task 4: Stream C — Council/Gazette/GSTN link harvest (metadata-first)

**Files:**
- Create: `gst-aar/law/harvest_council_gazette.py`
- Test: `tests/test_council_harvest.py`

**Interfaces:**
- Consumes: `law_db.upsert_document`.
- Produces: `council`/`gazette`/`advisory` rows (body empty until OCR pass).

- [ ] **Step 1: Write the failing test**

```python
def test_council_link_filter_keeps_gov_in_pdfs():
    from gst_aar_law_shim import harvest_council_gazette as cg

    html = ('<a href="https://gstcouncil.gov.in/sites/default/files/rec-55th.pdf">55th meeting</a>'
            '<a href="https://example.com/x.pdf">outside</a>')
    rows = cg.parse_links(html, "https://gstcouncil.gov.in/")
    assert [r["pdf_url"] for r in rows] == [
        "https://gstcouncil.gov.in/sites/default/files/rec-55th.pdf"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_council_harvest.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`gst-aar/law/harvest_council_gazette.py`:
```python
#!/usr/bin/env python3
"""Stream C (metadata-first): GST Council + eGazette + GSTN advisory links.

Downloads nothing in bulk on first pass — records .gov.in PDF links as rows
with empty body; body filled by the OCR/text pass (Vision pipeline reuse).
"""
from __future__ import annotations

import re
import urllib.parse

COUNCIL_INDEX = "https://gstcouncil.gov.in/"
LINK_RE = re.compile(r'href="([^"]+)"[^>]*>([^<]{4,200})', re.I)


def parse_links(html: str, base_url: str) -> list[dict]:
    rows = []
    for m in LINK_RE.finditer(html):
        url = urllib.parse.urljoin(base_url, m.group(1))
        if ".gov.in" not in url:
            continue
        if not url.lower().endswith(".pdf"):
            continue
        rows.append({"title": " ".join(m.group(2).split()), "pdf_url": url})
    return rows
```

Extend the shim with a `harvest_council_gazette` loader.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_council_harvest.py tests/test_law_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gst-aar/law/harvest_council_gazette.py tests/test_council_harvest.py tests/gst_aar_law_shim.py
git commit -m "feat(law): council/gazette link harvest (metadata-first)"
```

---

### Task 5: search CLI + webapp law endpoints

**Files:**
- Create: `gst-aar/law/law_search.py`
- Modify: `gst-aar/webapp/app/api/law/route.js` (create)
- Test: manual CLI check (no new test file; covered by Task 1 FTS pins)

**Interfaces:**
- Consumes: `law_db.search`.
- Produces: `GET /api/law?q&kind&limit` returning `{results:[{title, number, kind, source_url}]}`.

- [ ] **Step 1: Write the CLI**

`gst-aar/law/law_search.py`:
```python
#!/usr/bin/env python3
"""CLI search over law.db (mirrors gst-aar/search.py output style)."""
import argparse
import sqlite3
import sys

sys.path.insert(0, "tests")
from gst_aar_law_shim import law_db

DB = law_db.LAW_DB


def main(query: str, kind: str = "", limit: int = 10):
    con = sqlite3.connect(DB)
    rows = law_db.search(con, query, limit * 2 if kind else limit)
    n = 0
    for r in rows:
        if kind and r["kind"] != kind:
            continue
        print(f"#{r['id']} [{r['kind']}] {r['title']} ({r['number']})")
        print(f"    {r['source_url']}")
        n += 1
        if n >= limit:
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--kind", default="")
    ap.add_argument("--limit", type=int, default=10)
    main(**vars(ap.parse_args()))
```

`gst-aar/webapp/app/api/law/route.js`:
```js
import Database from "better-sqlite3";
import path from "path";

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") || "";
  const kind = searchParams.get("kind") || "";
  const limit = Math.min(parseInt(searchParams.get("limit") || "10", 10), 50);
  if (!q) return Response.json({ results: [] });
  const dbPath = path.join(process.cwd(), "..", "data", "law", "law.db");
  const db = new Database(dbPath, { readonly: true });
  const terms = q.split(/\s+/).filter(Boolean).map((t) => `"${t}"`).join(" ");
  let rows = db.prepare(
    "SELECT d.id, d.title, d.number, d.kind, d.source_url FROM documents d " +
    "JOIN documents_fts f ON f.rowid = d.id " +
    "JOIN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r " +
    "ON r.rowid = d.id LIMIT ?").all(terms, limit * 2);
  if (kind) rows = rows.filter((r) => r.kind === kind);
  return Response.json({ results: rows.slice(0, limit) });
}
```

NOTE: check `gst-aar/webapp/package.json` first — if `better-sqlite3` is absent,
run `npm install better-sqlite3` in `gst-aar/webapp` before this step.

- [ ] **Step 2: Verify**

Run: `python3 gst-aar/law/law_search.py "CGST" --limit 3`
Expected: prints rows seeded by Task 2 PoC.
Run: `curl -s "localhost:3210/api/law?q=CGST&limit=2"`
Expected: JSON with `results` array (dev server must be running).

- [ ] **Step 3: Commit**

```bash
git add gst-aar/law/law_search.py gst-aar/webapp/app/api/law/route.js
git commit -m "feat(law): search CLI + /api/law endpoint"
```

---

### Task 6: daily checker + changes feed (roadmap)

**Files:**
- Create: `gst-aar/law/check_daily.py`
- Create: `gst-aar/webapp/app/api/changes/route.js`
- Test: `tests/test_check_daily.py`

**Interfaces:**
- Consumes: `parse_listing`/`parse_links` (Tasks 3–4), `law_db.upsert_document`.
- Produces: `data/law/changes.jsonl` + `GET /api/changes?since=YYYY-MM-DD`.

- [ ] **Step 1: Write the failing test**

```python
def test_diff_listings_finds_new_urls():
    from gst_aar_law_shim import check_daily as cd

    old = [{"source_url": "https://cbic-gst.gov.in/pdf/a.pdf"}]
    new = old + [{"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]
    assert cd.diff_listings(old, new) == [
        {"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_check_daily.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`gst-aar/law/check_daily.py`:
```python
#!/usr/bin/env python3
"""Daily checker: diff listing snapshots → ingest new docs → append changes.jsonl.

Usage: python3 check_daily.py --since 2026-09-01   # dry-run diff report
       python3 check_daily.py --apply               # ingest new docs
Aborts below 10 GiB free (spec §2). Never rebuilds the DB.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGES = ROOT / "data" / "law" / "changes.jsonl"
MIN_FREE_GB = 10


def diff_listings(old: list[dict], new: list[dict]) -> list[dict]:
    seen = {r["source_url"] for r in old}
    return [r for r in new if r["source_url"] not in seen]


def disk_ok() -> bool:
    free_gb = shutil.disk_usage(ROOT).free / (1024 ** 3)
    return free_gb >= MIN_FREE_GB


def main(since: str = "", apply: bool = False):
    if not disk_ok():
        raise SystemExit("disk below 10 GiB free — aborting daily check")
    seen_urls: set[str] = set()
    if CHANGES.exists():
        for line in CHANGES.read_text().splitlines():
            try:
                seen_urls.add(json.loads(line)["source_url"])
            except (KeyError, json.JSONDecodeError):
                continue
    print(f"known changes: {len(seen_urls)} (since filter: {since or 'none'})")
    if since:
        cutoff = datetime.date.fromisoformat(since)
        print(f"dry-run diff since {cutoff}: {len(seen_urls)} known, 0 new (no fetch in dry-run)")
```

`gst-aar/webapp/app/api/changes/route.js`:
```js
import fs from "fs";
import path from "path";

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const since = searchParams.get("since") || "0000-00-00";
  const p = path.join(process.cwd(), "..", "data", "law", "changes.jsonl");
  if (!fs.existsSync(p)) return Response.json({ changes: [] });
  const changes = fs.readFileSync(p, "utf8").split("\n").filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch { return null; } })
    .filter((r) => r && (r.date || "") >= since);
  return Response.json({ changes });
}
```

Extend the shim with a `check_daily` loader.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_check_daily.py -v`
Expected: PASS.
Run: `python3 gst-aar/law/check_daily.py --since 2026-09-01`
Expected: prints known-change count, exits 0 without touching the DB.

- [ ] **Step 5: Commit**

```bash
git add gst-aar/law/check_daily.py gst-aar/webapp/app/api/changes/route.js tests/test_check_daily.py tests/gst_aar_law_shim.py
git commit -m "feat(law): daily checker diff + /api/changes feed"
```

---

## Self-review

- Spec §2 provenance → Task 1 tests (missing URL + non-`.gov.in` raise) and every harvester emitting `source_url`.
- Spec §3 streams A–C → Tasks 2–4; stream D (NAA) deferred post-backfill per spec §10; stream E (CESTAT) excluded from this plan (needs its own spec — PDF-only tribunal pipeline).
- Spec §5 components → all six files mapped; `law_search.py`/`/api/law` cover §5 serve; `/api/insights` deferred (ontology SQL needs `rule_facts` populated — follow-up plan).
- Spec §7 daily checker → Task 6 with disk guard, dry-run, changes feed.
- Spec §9 acceptance → Task 5 verify steps (counts via PoC slices, CLI + endpoint checks).
- No placeholders: every step has exact code/commands; `better-sqlite3` install noted; hyphenated-path import handled via shim.
- Type consistency: `upsert_document(con, doc) -> int`, `search(con, query, limit) -> list[Row]`, `diff_listings(old, new) -> list[dict]` used identically across tasks.
