#!/usr/bin/env python3
"""Stream A: harvest the CBIC statute layer from taxinformation.cbic.gov.in.

Two modes:
  --limit N   acts only (the original PoC path, kept for the fixture tests)
  --full      the whole statute hierarchy: acts, chapters, sections, rules,
              rule chapters, rule sections, amendment histories, regulations
              and forms.

TLS: the host serves a leaf issued by "Sectigo Public Server Authentication CA
OV R36" and omits the intermediate. The AIA URL is
http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt; that
certificate lives in `certs/` and `_https.py` loads it. Plain urllib fails with
CERTIFICATE_VERIFY_FAILED without it.

Text note: the section records carry `contentData: null` and only a
`contentFilePath` (a `tax_repository/...html` path that 404s). No API endpoint
exposes the section body — probed 2026-09-14 — so this harvest stores the
**structured hierarchy** (number, heading, act, chapter, amendment date) and
leaves the body to a future extraction. That is still the searchable skeleton:
section headings become findable, which is what the corpus lacked.

Usage: python3 harvest_cbic_api.py --full
       python3 harvest_cbic_api.py --limit 5
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://taxinformation.cbic.gov.in"
ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "law" / "acts"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

# endpoint -> (kind, human noun)
ENDPOINTS = {
    "cbic-act-msts": ("cbic_act", "Act"),
    "cbic-act-chapter-msts": ("cbic_act_chapter", "Chapter"),
    "cbic-act-section-msts": ("cbic_act_section", "Section"),
    "cbic-rule-msts": ("cbic_rule", "Rules"),
    "cbic-rule-chapter-msts": ("cbic_rule_chapter", "Rule chapter"),
    "cbic-rule-section-msts": ("cbic_rule_section", "Rule"),
    "cbic-amendment-doc-histories": ("cbic_amendment", "Amendment"),
    "cbic-regulation-msts": ("cbic_regulation", "Regulation"),
    "cbic-form-msts": ("cbic_form", "Form"),
}

# An act is GST law if its name matches this. Everything else in the CBIC
# repository (Customs, Central Excise, Customs Tariff, Provisional Collection,
# Chapter V of the Finance Act) is tagged non-GST so it does not surface in
# GST answers — the same convention /api/chat already filters on.
GST_ACT_RE = re.compile(
    r"goods\s*(?:and|&)\s*services\s*tax|compensation to states"
    r"|one hundred and first amendment", re.I)


def _load_law_db():
    spec = importlib.util.spec_from_file_location(
        "law_db", Path(__file__).parent / "law_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _https_opener():
    spec = importlib.util.spec_from_file_location(
        "_https_cbic", Path(__file__).parent / "_https.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.session()


def _req(url: str, token: str | None = None, data: bytes | None = None,
         op=None, retries: int = 3) -> bytes:
    headers = dict(UA)
    if token:
        headers.update(auth_headers(token))
    opener = op or _https_opener()
    for i in range(retries):
        _thr.wait(url)
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with opener.open(req, timeout=60) as r:
                blob = r.read()
            _thr.on_success(url)
            return blob
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_token(base: str = BASE, op=None) -> str:
    raw = _req(base + "/api/authenticate-token", data=b"{}", op=op)
    payload = json.loads(raw.decode("utf-8", "replace"))
    for key in ("id_token", "token", "access_token"):
        if payload.get(key):
            return payload[key]
    raise RuntimeError(f"no token in auth response keys: {sorted(payload)}")


def fetch_paged(base: str, token: str, path: str, page: int = 0,
                size: int = 50, op=None) -> list[dict]:
    sep = "&" if "?" in path else "?"
    raw = _req(f"{base}{path}{sep}page={page}&size={size}", token, op=op)
    payload = json.loads(raw.decode("utf-8", "replace"))
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("content", "data", "result"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def fetch_all(base: str, token: str, endpoint: str, op=None) -> list[dict]:
    """The API ignores page/size and returns the full set in one response."""
    return fetch_paged(base, token, f"/api/{endpoint}", op=op)


def normalize_acts(rows: list[dict]) -> list[dict]:
    docs = []
    for r in rows:
        name = r.get("actName") or r.get("name") or ""
        if not name:
            continue
        # Live API keys rows by `id` (brief fixture uses `actId`); accept both.
        act_id = r.get("actId") or r.get("id") or ""
        if not act_id:
            continue
        docs.append({
            "source_url": f"{BASE}/content-page/explore-act/{act_id}/1000001",
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


# --- full statute layer ------------------------------------------------------

def _date_of(rec: dict) -> str:
    for k in ("issueDt", "amendDt", "amendmentDt", "createdDt"):
        v = rec.get(k)
        if isinstance(v, str) and len(v) >= 10:
            return v[:10]
    return ""


def _nested_id(rec: dict, key: str) -> str:
    v = rec.get(key)
    if isinstance(v, dict):
        return str(v.get("id") or "")
    return str(v or "")


def label_of(kind: str, rec: dict) -> str:
    """Human heading for a record, from the keys that endpoint actually uses."""
    def g(*keys):
        for k in keys:
            v = rec.get(k)
            if isinstance(v, str) and v.strip():
                return " ".join(v.split())
        return ""

    if kind == "cbic_act":
        return g("actName", "actNameHi")
    if kind in ("cbic_act_chapter", "cbic_rule_chapter"):
        no, name = g("chapterNo"), g("chapterName")
        return f"Chapter {no} — {name}".strip(" —") if no else name
    if kind in ("cbic_act_section", "cbic_rule_section"):
        no, name = g("sectionNo"), g("sectionName")
        return f"{no} — {name}".strip(" —") if no else name
    if kind == "cbic_rule":
        no, name = g("ruleDocNo"), g("ruleDocName")
        return f"{no} — {name}".strip(" —") if no else name
    if kind == "cbic_amendment":
        return g("htmlFileName", "pdfFileName") or g("contentType")
    return g("ruleDocName", "contentFileName", "title", "name")


def normalize_full(endpoint: str, rows: list[dict],
                   act_names: dict[str, str]) -> list[dict]:
    """Turn one endpoint's rows into law.db documents."""
    kind, noun = ENDPOINTS[endpoint]
    docs = []
    for r in rows:
        rec_id = r.get("id")
        if rec_id is None:
            continue
        act_id = _nested_id(r, "actId") or _nested_id(r, "cbicTaxMst")
        act_name = act_names.get(act_id, "")
        label = label_of(kind, r)
        if not label:
            continue
        number = (r.get("sectionNo") or r.get("chapterNo")
                  or r.get("ruleDocNo") or r.get("actNo") or "")
        # A readable, searchable body built from the structured fields. There is
        # no section text to store (see module docstring), so this is the
        # hierarchy itself, phrased so FTS can match a heading.
        parts = [f"{noun}: {label}"]
        if act_name:
            parts.append(f"Act: {act_name}")
        if r.get("chapterName"):
            parts.append(f"Chapter: {r['chapterName']}")
        if r.get("ruleDocName") and kind != "cbic_rule":
            parts.append(f"Rules: {r['ruleDocName']}")
        if r.get("ruleCategory"):
            parts.append(f"Category: {r['ruleCategory']}")
        d = _date_of(r)
        if d:
            parts.append(f"Amended: {d}")
        docs.append({
            # The per-record API URL is a stable .gov.in address that returns
            # this exact record, so it is a legitimate provenance back-link.
            "source_url": f"{BASE}/api/{endpoint}/{rec_id}",
            "kind": kind,
            "title": label[:300],
            "number": str(number)[:60],
            "pub_date": d,
            "local_path": "",
            "sha256": hashlib.sha256(
                json.dumps(r, sort_keys=True, default=str).encode()).hexdigest(),
            "body": "\n".join(parts),
            "_non_gst": bool(act_name) and not GST_ACT_RE.search(act_name),
        })
    return docs


def main_full() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    law_db = _load_law_db()
    con = law_db.init_db()
    con.executescript("""CREATE TABLE IF NOT EXISTS law_tags (
        id INTEGER PRIMARY KEY,
        doc_id INTEGER NOT NULL REFERENCES documents(id),
        tag TEXT NOT NULL, UNIQUE(doc_id, tag));""")
    op = _https_opener()
    token = get_token(op=op)
    print(f"token ok ({len(token)} chars)", flush=True)

    acts = fetch_all(BASE, token, "cbic-act-msts", op=op)
    act_names = {str(a.get("id")): (a.get("actName") or "") for a in acts}
    print(f"acts: {len(acts)}", flush=True)

    grand, non_gst = 0, 0
    for endpoint in ENDPOINTS:
        try:
            rows = fetch_all(BASE, token, endpoint, op=op)
        except Exception as e:
            print(f"  {endpoint}: FAILED {type(e).__name__}: {str(e)[:80]}",
                  file=sys.stderr)
            continue
        docs = normalize_full(endpoint, rows, act_names)
        for d in docs:
            non = d.pop("_non_gst", False)
            doc_id = law_db.upsert_document(con, d)
            if non:
                con.execute("INSERT OR IGNORE INTO law_tags (doc_id, tag)"
                            " VALUES (?, 'non-GST')", (doc_id,))
                non_gst += 1
        con.commit()
        grand += len(docs)
        print(f"  {ENDPOINTS[endpoint][0]:20s} {len(rows):>5} rows -> {len(docs):>5} docs",
              flush=True)

    print(f"done: {grand} CBIC statute documents ({non_gst} tagged non-GST)")


def main(limit: int = 0, full: bool = False):
    if full:
        main_full()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    token = get_token()
    seen, total, page = set(), 0, 0
    law_db = _load_law_db()
    con = law_db.init_db()
    try:
        while True:
            rows = fetch_paged(BASE, token, "/api/cbic-act-msts", page)
            if not rows:
                break
            new_in_page = 0
            for r in rows:
                docs = normalize_acts([r])
                if not docs:
                    continue
                doc = docs[0]
                if doc["source_url"] in seen:
                    continue
                seen.add(doc["source_url"])
                law_db.upsert_document(con, doc)
                act_id = r.get("actId") or r.get("id") or ""
                (OUT / f"{act_id}.json").write_text(
                    json.dumps(r, ensure_ascii=False), encoding="utf-8")
                total += 1
                new_in_page += 1
                if limit and total >= limit:
                    print(f"PoC slice done: {total} acts")
                    return
            print(f"page {page}: {len(rows)} rows (total {total})")
            if new_in_page == 0:
                # API ignores page/size (repeats the same rows): no progress = done.
                print(f"no new rows on page {page}, stopping")
                break
            page += 1
    finally:
        con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    main(limit=args.limit, full=args.full)
