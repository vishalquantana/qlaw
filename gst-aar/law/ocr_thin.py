#!/usr/bin/env python3
"""Vision-OCR the thin (scanned) law PDFs. macOS-local, no LM Studio needed.

Finds law.db documents with empty bodies whose PDFs exist, renders pages via
fitz, OCRs with macOS Vision (same engine as extract_vision.py), writes texts
to data/law/text/ocr/ and upserts bodies. Idempotent: skips docs that already
have bodies.

Usage: gst-aar/ocr-benchmark/venv-tools/bin/python gst-aar/law/ocr_thin.py [--max N]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path

LAW = Path(__file__).parent
ROOT = LAW.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, LAW.parent / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(max_files: int = 0) -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))
    from gst_aar_law_shim import law_db
    ev = _load("extract_vision", "extract_vision.py")
    import fitz

    con = law_db.init_db()
    rows = con.execute(
        "SELECT id, local_path FROM documents WHERE body='' AND local_path != ''"
    ).fetchall()
    out = ROOT / "data" / "law" / "text" / "ocr"
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for doc_id, local in rows:
        p = Path(local)
        if not p.is_absolute():
            p = ROOT.parent / p
        if not p.exists():
            continue
        t0 = time.time()
        try:
            doc = fitz.open(p)
            pages = []
            with tempfile.TemporaryDirectory() as td:
                for i, page in enumerate(doc):
                    img = os.path.join(td, f"p{i:02d}.png")
                    page.get_pixmap(dpi=150).save(img)
                    pages.append(ev.vision_ocr_image(img))
            doc.close()
            text = "\n\n".join(pages).strip()
        except Exception as e:
            print(f"  error {p.name}: {type(e).__name__}", file=sys.stderr)
            continue
        if len(text) < 200:
            print(f"  still thin {p.name} ({len(text)}ch)", file=sys.stderr)
            continue
        (out / (p.stem + ".txt")).write_text(text, encoding="utf-8")
        con.execute("UPDATE documents SET body=? WHERE id=?", (text, doc_id))
        con.commit()
        done += 1
        print(f"  {done}: {p.name} {len(text)}ch in {time.time()-t0:.0f}s")
        if max_files and done >= max_files:
            break
    print(f"done: {done} OCR'd")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max_files", type=int, default=0)
    main(**vars(ap.parse_args()))
