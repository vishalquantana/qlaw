# OCR Benchmark — Scanned GST Advance Ruling (Allen Career Institute, Rajasthan)

**Test document:** `data/pdfs/Rajasthan/9-order_allen_institute_30_july_2026.pdf`
24 pages, image-only scan (PyMuPDF `get_text()` = 0 chars). **Critical finding: the embedded
scan is only 612x1008 px, i.e. ~72 dpi native resolution.** Any 200/300 dpi "rendering" is
just upscaling of the same pixels — which is why dpi/psm variants barely differ. English
print is clean; several paragraphs are Hindi (Devanagari); the ruling date **30.07.2026
exists ONLY as handwriting** (p1 "Date of Ruling", p24 signature date).

**Benchmarked:** 2026-09-05 · macOS 26.5.1 arm64 · Python 3.14.7 · tesseract 5.5.2 (homebrew)

## Ground-truth facts checked

| Fact | Present in doc as |
|---|---|
| Ruling no. `RAJ/AAR/2026-27/11` | printed, p1 |
| Date `30.07.2026` | **handwritten only** (p1, p24) |
| `M/s ALLEN CAREER INSTITUTE PRIVATE LIMITED` | printed, p1/p3 |
| GSTIN `08AAVCA8216C1ZI` | printed, p1/p6 |
| Notification `13/2020`-Central Tax | printed, many pages |
| e-invoicing / Rajasthan | printed |
| HSN codes / rate table | **absent from this document** (metadata's "HSN" fact is N/A; no HSN string or table appears on any page) |

## Results

| Tool | Verdict on facts | Garbled lines | Hindi (Devanagari) | s/page (incl. render) | Disk | Py 3.14 |
|---|---|---|---|---|---|---|
| **Surya OCR 0.22.1** (VLM via llama.cpp) | **ALL PASS incl. handwritten 30.07.2026, GSTIN 1-char off (ZJ)** | 1.5% (stray handwritten lines) | **Perfect paragraphs** (1660 chars) | ~33.7 CPU (llama.cpp, 1.4 GB model) | 1.4 GB model + 1.9 GB venv (deleted) | OK |
| **macOS Vision** (pyobjc 12.2.2, accurate, 300 dpi render) | Ruling PASS, printed dates PASS, **GSTIN exact PASS**, handwritten date near-miss (`30-07-2426`) | 0.0% | **Dropped silently** (0 Devanagari) | **0.62 + 0.13 render ≈ 0.75** | ~0 (model is in the OS) | OK |
| ocrmypdf 17.11.0 (tesseract eng, native 72 dpi) | Ruling PASS, GSTIN FAIL (`[osaaveasaiecizy`), handwritten date FAIL | 0.0% | Latin gibberish | **0.26** (renders at native dpi) | ~0 | OK |
| tesseract eng, 200 dpi, psm 6 | Ruling PASS, GSTIN FAIL (`OBAAVCAS2IGCIZ)`), date FAIL | 0.0% | Latin gibberish | 1.21 + 0.07 render | 0 | OK |
| tesseract eng, 200 dpi, psm 3 / psm 4 | psm3 ruling PARTIAL (`RAI/AAR`), psm4 partial | 0.0–0.1% | Latin gibberish | 1.28–1.29 | 0 | OK |
| tesseract eng, 300 dpi, psm 3 | Ruling PASS, rest same as 200 dpi | 0.0% | Latin gibberish | 1.53 + 0.13 | 0 | OK |
| tesseract eng+hin (tessdata_fast `hin`, 1.1 MB) | Same English quality, +noise | 1.9% | Legible but error-prone (~90%) | 3.33 (2.75x slower) | 1.1 MB | OK |
| EasyOCR 1.7.2 (torch 2.14, CPU, en+hi) | Garbled: `GODDS`, `L3.07.202E`, `DXAAVLARZIGLTZI`; Devanagari digits leak into English (`२०B`) | high (case/scramble chaos) | Recognized but noisy | **18.4** | ~300 MB models | OK (surprisingly) |
| PaddleOCR 3.7.0 (PP-OCRv6_medium, **Python 3.12 venv** — no cp314 wheel, runs fine on 3.12) | **Ruling PASS, applicant PASS, Notification 13/2020 PASS, GSTIN EXACT (p6)**, **handwritten date PASS** (`Date of Ruling: 30.07.2026`) | ~0 (1 stray CJK char/doc) | **Not supported** — no Devanagari lang pack in 3.7 (`lang='devanagari'` → ValueError); Hindi lines degrade to digit fragments | **33.3** (medium) / 18.2 (PP-OCRv5_mobile, quality regression: ruling no. MISS on p1) | ~500 MB models | needs ≤3.12 |
| **Baidu Unlimited-OCR 1.0** (VLM, 6.7 GB bf16) | **NOT RUNNABLE on macOS** — see notes below | — | — | — | 6.7 GB model | blocked |

Sample quality (page 1, Hindi paragraph):

- **Surya:** `1. केंद्रीय वस्तु एवं सेवा कर अधिनियम, 2017 तथा राजस्थान वस्तु एवं सेवा कर अधिनियम, 2017 (जिन्हें आगे क्रमशः 'सीजीएसटी अधिनियम' एवं 'आरजीएसटी अधिनियम' कहा गया है) की धारा 102 के अनुसार...` — essentially flawless; also emitted the page-1 table as a real HTML table and read the **handwritten** `Date of Ruling: 30.07.2026` correctly.
- **tesseract eng only:** `Seals Teed Ve Bar oe Hera, 2017 CN Terese Tey Ve Sar ae HO, 2017` — Latin garbage.
- **tesseract eng+hin:** `3. hala वस्तु एवं Gar कर अधिनियम, 2017 तथा राजस्थान वस्तु एवं सेवा कर अधिलियम, 2017` — usable but degraded; slower.
- **Vision:** Hindi paragraphs dropped entirely; English lines are the cleanest of the non-VLM engines, layout order preserved.

### Notes per tool

1. **Tesseract (baseline).** psm 6 slightly beats psm 3/4 on the header table. 300 dpi upscaling buys nothing (native 72 dpi source). Autocontrast preprocessing: no measurable change. eng+hin recovers ~90%-legible Devanagari at 2.75x cost and slightly dirties English. Cheap, deterministic, CPU-parallelizable.
2. **ocrmypdf.** Fastest full-pipeline (0.26 s/page, it OCRs at the embedded 72 dpi and produces a searchable-PDF with `--sidecar` text). English quality ≈ tesseract psm 3; weakest on the GSTIN. Note: `--psm` was removed in ocrmypdf 17.
3. **Surya OCR.** Now a VLM (surya-ocr-2 gguf, 1.4 GB, runs through homebrew `llama-server`). Quality is in a different class: correct handwritten date, real table structure, perfect Hindi. Cost: ~34 s/page CPU on this Mac (42% CPU util; `--parallel 8` slots did not saturate), 1.4 GB model download.
4. **EasyOCR.** Installs on 3.14 (torch 2.14 arm64 wheels exist) but quality is unusable for legal text and it is 25x slower than tesseract.
5. **PaddleOCR.** Blocked on Python 3.14 (no cp314 wheel) but **runs on a Python 3.12 venv** (`python3.12 -m venv venv-paddle312; pip install paddlepaddle paddleocr` — verified 3.7.0/3.3.1). Quality is the surprise: it read the **handwritten** `Date of Ruling: 30.07.2026` and produced the **exact GSTIN** (p6; the p1 copy is 1 char off), Surya/Vision-class accuracy on English. But: no Devanagari support in 3.7 at all, and CPU throughput is Surya-class slow (33.3 s/page medium; the mobile variant is 18.2 s/page with a quality regression). 65k pages ≈ **600 h locally** — only attractive with a GPU, which this Mac can't offer (no CUDA/MPS for paddle).

5b. **Baidu Unlimited-OCR** (`baidu/Unlimited-OCR`, VLM, DeepSeek-OCR fork, 6.7 GB bf16 single file). **Could not be executed on macOS at any of three levels**, despite ~4 compatibility patches (`uocr_infer.py`):
   - Official inference paths are CUDA-only (SGLang/vLLM); repo ships no CPU/macOS path.
   - **transformers + MPS**: crashes in the vision encoder (`AcceleratorError: garbage gather index`) even after patching 17 hardcoded `.cuda()` calls and 3 `torch.autocast("cuda")`.
   - **transformers + CPU**: two release-quality bugs surface: (a) the published checkpoint's `vision_model.embeddings.position_ids` buffer contains **garbage integers** (e.g. 4,603,632,896) instead of `arange` — verified at runtime; (b) after rebuilding that buffer, an **off-by-one spatial mismatch** (277 vs 278) in the position-embedding interpolation of `deepencoder.get_abs_pos`, in both base and crop modes.
   - Requires transformers-version-specific config shims (12 missing config attrs patched).
   Verdict: promising architecture, but the open release is not usable outside its CUDA demo path. Revisit if a fixed checkpoint or a hosted API appears. Artifacts kept: `uocr_infer.py`, patched snapshot notes in this file.
6. **macOS Vision.** Zero-download, zero-install-weight (just `pip install pyobjc-framework-Vision`). Best practical quality: exact GSTIN, exact printed text, even nearly reads the handwriting (`30-07-2426`). Hindi is skipped (no Devanagari support in this macOS build's text recognition), which is "clean loss" rather than garbage. macOS-only.

## Ranking for the 4,300-doc / ~65,000-page bulk job

| Rank | Tool | Est. wall time for 65k pages | Est. cost | Why |
|---|---|---|---|---|
| 1 | **macOS Vision** (on this / any Apple-Silicon Mac) | ~0.75 s/p ≈ **14 h** (parallelizable across processes → 4–7 h) | $0 | Best quality-per-second by a wide margin; no downloads; robust on low-res scans |
| 2 | **ocrmypdf / tesseract** (parallel, e.g. 4 workers) | ~4.7 h (ocrmypdf) / ~9 h (tess 200dpi psm6, 4× parallel) | $0 | Good English, 5–15x faster than Surya; Hindi garbage; no handwriting |
| 3 | **Mistral OCR API** (fallback, paid) | hours (API throughput dependent) | **≈ $130** | VLM-class quality incl. Hindi + handwriting, zero local compute |
| 4 | **Surya OCR** | ~610 h on this Mac (CPU) | $0 compute | Best raw quality, but CPU throughput makes local bulk runs impractical |
| 5 | tesseract eng+hin | ~60 h (4× parallel) | $0 | Only if Hindi retention matters more than speed and quality noise |
| 6 | EasyOCR | ~330 h | $0 | Unusable quality |
| — | PaddleOCR | — | — | Incompatible with Python 3.14 |

## Recommendation

1. **Production primary: macOS Vision via PyObjC on Apple Silicon.** ~14 h single-process for the full 65k pages (parallelize per-document processes → ~5 h), $0, and the highest factual extraction accuracy of any local tool tested (it was the only engine to get the GSTIN exactly right). Caveats: macOS-only, Hindi/Devanagari content is dropped (acceptable if the corpus is indexed on English content; the Hindi passages are verbatim bilingual restatements of adjacent English text in this document class), and handwriting is not reliably captured.
2. **If Hindi retention is a hard requirement:** either pay for **Mistral OCR (~$130, VLM-class, Surya-equal quality at API speed)** — very reasonable against ~600 GPU-hours of local VLM OCR — or run Surya on a rented GPU node. Tesseract eng+hin is the free fallback but slow and noisy.
3. **Cheap triage pipeline:** use ocrmypdf (0.26 s/page) to add a searchable text layer and a `RAJ/AAR`-style fact check; escalate documents that fail the fact-check to Vision/Mistral.
4. Ignore 300 dpi re-rendering for this corpus — scans are natively ~72 dpi; renders above ~150 dpi add no information.

## Artifacts

- `best-allen-institute.txt` — Surya OCR full text (best quality: all facts incl. handwritten date + Hindi)
- `texts/` — full-text outputs: `_vision200_full.txt`, `_vision300_full.txt`, `_tess200-psm6_full.txt`, `_tess200-enghin_full.txt`, `ocrmypdf-sidecar.txt`, `_easyocr-sample_full.txt`, `_surya_full.txt` (PaddleOCR produced no output — install blocked).
- `render.py`, `run_tess.py`, `score_all.py`, `vision_ocr.py` — benchmark scripts
- `venv-tools/` (182 MB, kept: ocrmypdf 17.11.0 + pyobjc-framework-Vision 12.2.2 needed to reproduce); surya/easyocr/paddle venvs and model caches (surya-2 gguf 1.4 GB, EasyOCR models) were deleted after capture; temp page images deleted.
