"""Render PDF pages to PNGs at various settings for OCR benchmarking."""
import sys, os, time
import fitz

PDF = "/Users/vishalkumar/Downloads/qlaw/gst-aar/data/pdfs/Rajasthan/9-order_allen_institute_30_july_2026.pdf"
OUT = "/Users/vishalkumar/Downloads/qlaw/gst-aar/ocr-benchmark/images"

def render(variant, pages=None):
    doc = fitz.open(PDF)
    os.makedirs(f"{OUT}/{variant}", exist_ok=True)
    t0 = time.time()
    n = 0
    for i, page in enumerate(doc):
        if pages and i not in pages:
            continue
        if variant == "200dpi-gray":
            pix = page.get_pixmap(dpi=200, colorspace=fitz.csGRAY)
        elif variant == "300dpi-gray":
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY)
        elif variant == "200dpi-rgb":
            pix = page.get_pixmap(dpi=200, colorspace=fitz.csRGB)
        elif variant == "300dpi-nodither-contrast":
            # 300dpi grayscale, no dither + higher contrast via matrix is not
            # directly supported; emulate contrast by rendering gray and letting
            # tesseract's own thresholding work. Usenodither + gamma-ish trick:
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY, alpha=False)
        n += 1
        pix.save(f"{OUT}/{variant}/p{i+1:02d}.png")
    dt = time.time() - t0
    print(f"{variant}: {n} pages in {dt:.2f}s ({dt/max(n,1)*1000:.0f} ms/page)")

if __name__ == "__main__":
    for v in sys.argv[1:]:
        render(v)
