#!/usr/bin/env python3
"""Extract machine-readable text from downloaded AAR/AAAR PDFs.

Two-tier extraction:
1. Native text layer via PyMuPDF (fitz) — instant, exact.
2. Tesseract OCR fallback for image-only pages (render @200dpi, --psm 4).
   English-only language pack: Hindi passages are garbled by default (v1
   limitation; upgrade path = Mistral OCR, see repo pipeline ocr-mistral.py).

Writes data/text/<state>/<name>.txt and appends to data/extract_status.jsonl
"""
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "data" / "pdfs"
TXT_DIR = ROOT / "data" / "text"
STATUS = ROOT / "data" / "extract_status.jsonl"

MIN_CHARS_PER_PAGE = 120  # below this a page counts as image-only
OCR_DPI = 200


def ocr_page(page: fitz.Page) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        page.get_pixmap(dpi=OCR_DPI).save(tmp_path)
        r = subprocess.run(
            ["tesseract", tmp_path, "stdout", "--psm", "4", "-l", "eng"],
            capture_output=True,
        )
        return r.stdout.decode("utf-8", "replace")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def extract_one(pdf_path: Path) -> dict:
    rel = pdf_path.relative_to(PDF_DIR)
    out = TXT_DIR / rel.with_suffix(".txt")
    status = {"pdf": str(rel)}
    if out.exists() and out.stat().st_size > 0:
        status.update(status="cached", chars=out.stat().st_size)
        return status
    try:
        doc = fitz.open(pdf_path)
        pages, ocr_pages, native_ok_pages = [], 0, 0
        for page in doc:
            native = page.get_text("text")
            if len(native.strip()) >= MIN_CHARS_PER_PAGE:
                native_ok_pages += 1
                pages.append(native)
            else:
                pages.append(ocr_page(page))
                ocr_pages += 1
        doc.close()
        text = "\n\n".join(pages).strip()
        status["pages"] = len(pages)
        status["ocr_pages"] = ocr_pages
        status["chars"] = len(text)
        if native_ok_pages == 0 and len(text) < 500:
            status["status"] = "ocr_failed"
        else:
            status["status"] = "ok"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except Exception as e:
        status.update(status=f"error_{type(e).__name__}", detail=str(e)[:200])
    return status


def main():
    pdfs = sorted(PDF_DIR.rglob("*.pdf"))
    print(f"{len(pdfs)} pdfs")
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    stats = {}
    mode = "a" if STATUS.exists() else "w"
    with STATUS.open(mode) as sf, ProcessPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(extract_one, p): p for p in pdfs}
        done = 0
        for fut in as_completed(futures):
            st = fut.result()
            sf.write(json.dumps(st, ensure_ascii=False) + "\n")
            sf.flush()
            key = st["status"].split("_")[0]
            stats[key] = stats.get(key, 0) + 1
            done += 1
            if done % 50 == 0:
                print(f"[{done}/{len(pdfs)}] {stats}", flush=True)
    print("DONE:", stats)


if __name__ == "__main__":
    main()
