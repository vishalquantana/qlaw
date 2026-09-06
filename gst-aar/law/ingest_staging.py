#!/usr/bin/env python3
"""Generic ingest for state staging dirs: extract text, upsert with dates, FTS-live.

Covers every gst-aar/data/law/staging/<state>/ with inventory.jsonl:
extracts text layers (thin files flagged for ocr_thin.py), parses number/date
from inventory cells or filename, upserts kind=<dir>-mapped documents.

Usage: python3 ingest_staging.py [--only odisha]   (idempotent, resumable)
Vectors come later via embed_law.py (needs LM Studio).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
STAGE = ROOT / "data" / "law" / "staging"
TEXT = ROOT / "data" / "law" / "text"

KIND_OF = {
    "telangana": "tg_notification", "west-bengal": "wb_notification",
    "odisha": "od_notification", "maharashtra": "mh_notification",
    "gujarat": "gj_notification", "rajasthan": "rj_notification",
    "delhi": "dl_notification", "kerala": "kl_notification",
    "karnataka": "ka_notification", "uttar-pradesh": "up_notification",
    "tamil-nadu": "tn_notification", "assam": "as_notification",
    "chhattisgarh": "cg_notification", "punjab": "pb_notification",
    "haryana": "hr_notification", "bihar": "br_notification",
}


def load_rows(inv: Path) -> list[dict]:
    rows = []
    for line in inv.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main(only: str = "") -> None:
    sys.path.insert(0, str(ROOT.parent / "tests"))
    from gst_aar_law_shim import law_db
    import fitz

    con = law_db.init_db()
    have_body = {r[0] for r in con.execute("SELECT source_url FROM documents WHERE body != ''")}
    total, thin = 0, 0
    for d in sorted(STAGE.iterdir()):
        if not d.is_dir() or (only and d.name != only):
            continue
        inv = d / "inventory.jsonl"
        if not inv.exists():
            continue
        kind = KIND_OF.get(d.name, d.name.replace("-", "_") + "_notification")
        out = TEXT / d.name
        out.mkdir(parents=True, exist_ok=True)
        for r in load_rows(inv):
            if r.get("source_url", "") in have_body:
                continue
            p = Path(r.get("local_path", ""))
            if not p.is_absolute():
                p = ROOT.parent / p
            if not p.exists():
                continue
            try:
                text = "\n\n".join(pg.get_text() for pg in fitz.open(p))
            except Exception:
                continue
            if len(text) < 500:
                thin += 1
                body = ""
            else:
                (out / (p.stem + ".txt")).write_text(text, encoding="utf-8")
                body = text
            cells = r.get("cells", [])
            blob = " ".join(cells[:5])
            number = next((c for c in cells[:3] if re.search(r"\d", c)), p.stem[:60])
            pub = ""
            m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", blob)
            if m:
                pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            subject = next((c for c in cells if len(c) > 25), number)
            law_db.upsert_document(con, {
                "source_url": r.get("source_url", ""), "kind": kind,
                "title": subject[:200], "number": number[:60], "pub_date": pub,
                "local_path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "body": body})
            total += 1
    print(f"ingested: {total} docs ({thin} thin, OCR queue)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    main(**vars(ap.parse_args()))
