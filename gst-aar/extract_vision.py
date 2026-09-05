#!/usr/bin/env python3
"""Production OCR: macOS Vision (via PyObjC) over downloaded AAR PDFs.

Per benchmark (ocr-benchmark/REPORT.md): Vision is the highest quality-per-second
local engine (0.75 s/page, exact GSTIN). Hindi/Devanagari is dropped — accepted
trade-off unless Mistral OCR is chosen.

Writes data/text/<State>/<name>.txt (overwrites the earlier tesseract output for
re-processed files; language of record is English) and appends per-file status to
data/extract_vision_status.jsonl. Resumable: skips files whose txt exists with
matching pdf mtime.

Requires: venv-tools (pyobjc-framework-Vision). Run:
    gst-aar/ocr-benchmark/venv-tools/bin/python extract_vision.py [--limit N]
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "data" / "pdfs"
TXT_DIR = ROOT / "data" / "text"
STATUS = ROOT / "data" / "extract_vision_status.jsonl"

# 0 = let macOS Vision decide; the scans are ~72 dpi native
RENDER_DPI = 150


def vision_ocr_image(img_path: str) -> str:
    """Run macOS Vision text recognition on one image, return text."""
    import Vision
    import objc

    with open(img_path, "rb") as f:
        data = f.read()

    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en-US"])
    request.setUsesLanguageCorrection_(True)

    ok = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision failed: {ok}")

    results = request.results() or []
    lines = []
    for obs in results:
        candidates = obs.topCandidates_(1)
        if candidates:
            lines.append(candidates[0].string())
    return "\n".join(lines)


def process_one(pdf_path: Path) -> dict:
    import fitz

    rel = pdf_path.relative_to(PDF_DIR)
    out = TXT_DIR / rel.with_suffix(".txt")
    pdf_mtime = pdf_path.stat().st_mtime
    status = {"pdf": str(rel)}

    if out.exists():
        # cached if written after the pdf's last modification (i.e. from same pdf version)
        if out.stat().st_mtime >= pdf_mtime and out.stat().st_size > 100:
            status.update(status="cached", chars=out.stat().st_size)
            return status

    try:
        doc = fitz.open(pdf_path)
        t0 = time.time()
        pages = []
        with tempfile.TemporaryDirectory() as td:
            for i, page in enumerate(doc):
                img = os.path.join(td, f"p{i:02d}.png")
                pix = page.get_pixmap(dpi=RENDER_DPI)
                pix.save(img)
                pages.append(vision_ocr_image(img))
        doc.close()
        text = "\n\n".join(pages).strip()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        status.update(
            status="ok", pages=len(pages), chars=len(text),
            seconds=round(time.time() - t0, 2), engine="macos_vision",
        )
    except Exception as e:
        status.update(status=f"error_{type(e).__name__}", detail=str(e)[:200])
    return status


def main():
    pdfs = sorted(PDF_DIR.rglob("*.pdf"))
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        pdfs = pdfs[:limit]
    print(f"{len(pdfs)} pdfs to OCR with macOS Vision")
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    stats = {}
    t0 = time.time()
    mode = "a" if STATUS.exists() else "w"
    with STATUS.open(mode) as sf, ProcessPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(process_one, p): p for p in pdfs}
        done = 0
        for fut in as_completed(futures):
            st = fut.result()
            sf.write(json.dumps(st, ensure_ascii=False) + "\n")
            sf.flush()
            key = st["status"].split("_")[0]
            stats[key] = stats.get(key, 0) + 1
            done += 1
            if done % 50 == 0 or done == len(pdfs):
                rate = done / max(time.time() - t0, 1)
                print(f"[{done}/{len(pdfs)}] {stats} ({rate:.2f} pdf/s)", flush=True)
    print(f"DONE in {(time.time()-t0)/60:.1f} min:", stats)


if __name__ == "__main__":
    main()
