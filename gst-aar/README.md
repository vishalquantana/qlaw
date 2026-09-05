# GST AAR Pipeline — Complete State & Restart Guide

> **THE restart-survival doc.** If everything crashed, start here.
> Last updated: 2026-09-06 ~02:30 (chatbot milestone).
> Companion docs: [../notes/official-sources.md](../notes/official-sources.md) (source
> catalog + CBIC deep-dive), [ocr-benchmark/REPORT.md](ocr-benchmark/REPORT.md) (OCR engine
> benchmark), [ocr-benchmark/benchmark.html](ocr-benchmark/benchmark.html) (shareable version).

---

## 1. What this project is

**Vision:** a rules-as-code SaaS on Indian law — business users describe their profile
(states, HSN/SAC codes, activities) and get told which legislation/rulings affect them,
with subscriptions/alerts, an API + MCP layer, all grounded in official sources.

**Current focus (priority 1, user-set):** the GST advance-ruling corpus — download all
AAR/AAAR orders from the GST Council, OCR them, make them searchable (SQLite FTS5 +
vectors), and serve a chatbot/search UI grounded in official references.

**Everything runs locally, $0:** LM Studio supplies the LLM + embeddings; macOS Vision
does OCR; SQLite is the only database.

## 2. Repository layout

```
/Users/vishalkumar/Downloads/qlaw/     = git repo, private: github.com/vishalquantana/qlaw
├── gst-aar/                           ← ALL our pipeline work lives here
│   ├── scrape_list.py                 crawler: GST Council listing pages → aar_list.jsonl
│   ├── download_pdfs.py               throttled PDF downloader → data/pdfs/<State>/
│   ├── extract_text.py                tesseract OCR (superseded, kept for fallback)
│   ├── extract_vision.py              ★ production OCR: macOS Vision via PyObjC
│   ├── embed_chunks.py                ★ chunks texts → nomic-embed via LM Studio → SQLite
│   ├── build_db.py                    builds aar.db (rulings + rulings_fts FTS5)
│   ├── fix_dates.py                   re-parses order dates in place (no DB rebuild)
│   ├── export_inventory.py            inventory.csv/jsonl: every doc + original source URL
│   ├── search.py                      CLI search (BM25)
│   ├── README.md                      this file
│   ├── data/
│   │   ├── aar_list.jsonl             2,888 unique ruling records (crawl COMPLETE)
│   │   ├── aar.db                     SQLite: rulings, rulings_fts, chunks, download_log
│   │   │                              (gitignored — >100MB, regenerable, see §7)
│   │   ├── pdfs/<State>/*.pdf         2,888 PDFs, 8.6 GB (gitignored, re-downloadable)
│   │   ├── text/<State>/*.txt         extracted texts (Vision OCR, in progress)
│   │   ├── extract_vision_status.jsonl  per-PDF OCR status (resumability)
│   │   ├── inventory.csv|.jsonl       provenance export
│   │   └── download_log (in aar.db)   every download: source_url→local_path→timestamp
│   ├── ocr-benchmark/                 12-engine OCR benchmark + REPORT.md + benchmark.html
│   │   └── venv-tools/                pyobjc+ocrmypdf venv (used by extract_vision.py!)
│   └── webapp/                        Next.js app (see §5)
├── notes/official-sources.md          inventory of ALL official sources encountered
└── (rest)                             open-india-law repo clone (Vaquill-AI) as reference
```

## 3. Current state (as of last update)

| Component | State |
|---|---|
| Listing crawl | ✅ COMPLETE — 2,888 unique rulings (308 pages; cross-page dupes dedupe) |
| PDF download | ✅ COMPLETE — 2,888/2,888, 8.6 GB, validated %PDF magic, download_log full |
| Vision OCR | 🔄 IN PROGRESS — check `wc -l data/extract_vision_status.jsonl` (target 2,888); resumable, see §4 |
| Embeddings | 🔄 PARTIAL — re-run `embed_chunks.py` after OCR (resumable, picks up new texts) |
| SQLite DB | ✅ rulings + FTS5 + chunks tables live; ⚠️ txt_file column over-counts until final rebuild |
| Webapp | ✅ RUNNING — http://localhost:3210 (search, semantic, chatbot) |
| LM Studio | ✅ RUNNING — :1234, models: ornith-1.5-35b-a3b (LLM), text-embedding-nomic-embed-text-v1.5 (768-dim) |
| Disk | ⚠️ WATCH IT — was 14 Gi free; corpus 8.8 GB. `df -h /System/Volumes/Data` before bulk steps |
| Git | pushed to private repo through commit fb6d128 |

**Known data quirk:** `rulings.txt_file` currently says 2,887 (set by an interim rebuild
while files were mid-OCR); the truth is whatever exists in `data/text/`. A final
`build_db.py` run after OCR completes fixes this — see §4 step 3.

## 4. The restart playbook (in order)

```bash
cd /Users/vishalkumar/Downloads/qlaw/gst-aar

# 1. If Vision OCR was interrupted, resume it (skips files with fresh .txt):
ocr-benchmark/venv-tools/bin/python extract_vision.py
#    → writes data/text/<State>/*.txt + extract_vision_status.jsonl (append mode)
#    → ~3.5 s/PDF with 4 workers; full corpus ≈ 3 h

# 2. When OCR is done (status file ≈ 2,888 lines), rebuild the DB cleanly.
#    ⚠️ build_db.py DELETES aar.db first — that also wipes chunks/embeddings, so:
#    2a. run build_db.py,  2b. then re-run embed_chunks.py (re-embeds everything)
python3 build_db.py
python3 embed_chunks.py                # resumable; ~1.6k-char chunks, batches of 32

# 3. Refresh exports:
python3 export_inventory.py

# 4. Start the webapp (if not running):
cd webapp && npm run dev               # port 3210

# 5. Ensure LM Studio server is up (it usually is):
curl http://localhost:1234/v1/models   # expect ornith… + nomic… models
```

Sanity checks after restart:
```bash
python3 search.py "hsn e-invoicing" --limit 3
curl -s "localhost:3210/api/search?q=hsn&limit=1" | head -c 200
curl -s "localhost:3210/api/semantic?q=gst rate on sculptures&limit=2" | head -c 300
```

## 5. The webapp (gst-aar/webapp — Next.js 15, port 3210)

Light-mode UI (globals.css design tokens). Features:
- **Keyword search** (FTS5 BM25) with state/date/full-text filters + pagination
- **Semantic search** — cosine over chunks (vectors cached in-process, keyed by count)
- **✦ Ask the corpus** — multi-turn RAG chatbot; grounded-only answers, inline [n]
  citations, source cards linking to official PDFs; suggested starters

API routes (the seeds of the public API):
| Route | What |
|---|---|
| `GET /api/search?q&state&from&to&hasText&limit&offset` | BM25 search + snippets + facets |
| `GET /api/semantic?q&limit` | vector similarity over chunks |
| `POST /api/chat {messages:[...]}` | multi-turn grounded RAG (hybrid retrieval + RRF) |
| `POST /api/ask {question}` | single-shot RAG (kept for API compat) |
| `GET /api/document?id=` | full record + OCR text |

Model config via env: `LMSTUDIO_URL` (default http://localhost:1234/v1), `LLM_MODEL`
(default ornith-1.5-35b-a3b).

## 6. Provenance rules (user-required, standing)

1. **Every document carries its ORIGINAL publisher URL** — in `rulings.pdf_url`,
   `download_log`, `inventory.csv/jsonl`. No source URL → no downstream processing.
2. **Inventory everything**: every official source encountered gets cataloged in
   `notes/official-sources.md` + a scraper as needed. CBIC deep-dive lives there
   (JHipster API behind taxinformation.cbic.gov.in; anonymous JWT via
   POST /api/authenticate-token; notifications endpoints were 500ing; fallback
   scrape cbic-gst.gov.in flat PDFs).
3. Data license: CC BY 4.0 attribution; scripts Apache-2.0 (open-india-law base).

## 7. Hard-won gotchas (do not rediscover these)

- **aar.db is gitignored** (112 MB > GitHub's 100 MB limit; rejected push). It's
  regenerable: build_db.py + embed_chunks.py from jsonl + text files. Same for
  data/pdfs/ (8.6 GB), ocr-benchmark venvs, preview PNGs.
- **Orphan processes**: killed background shells left Python children running
  (a downloader finished the whole corpus "by itself"; an old tesseract extractor
  kept writing). Always `ps aux | grep -E "extract|download|scrape"` after kills.
- **`build_db.py` DELETES aar.db** before rebuilding — never run it while you care
  about the chunks/embeddings tables; patch in place (fix_dates.py pattern) instead.
- **extract_* status files are append-mode** → delete the .jsonl for a clean pass.
- **FTS5 hyphens**: "e-invoicing" parses as column syntax; always quote terms.
- **Git dates**: order numbers with digit runs produced dates like 3646-23-22;
  split_order_field now sanity-validates (fix_dates.py patched existing rows).
- **Disk**: this Mac runs ~97% full. Check before bulk steps; PoC first (user rule).
- **India Code geo-blocks** non-IN IPs (intermittently); CBIC has an F5 WAF that
  blocks non-browser POSTs (TLS fingerprinting) → Playwright when needed.
- **Scans are ~72 dpi native** — rendering >150 dpi adds nothing (benchmark finding).

## 8. Benchmark conclusion (ocr-benchmark/REPORT.md + benchmark.html)

12 engines/variants tested on a 24-page scanned ruling (72 dpi, handwritten date):
- **Winner: macOS Vision** — 0.75 s/page, exact GSTIN, $0 → production engine
- Surya VLM & PaddleOCR (py3.12!) — 5/5 quality but ~600 h locally
- Baidu Unlimited-OCR — not runnable on macOS (checkpoint bug, MPS crash)
- tesseract-class — 2/5 facts; ocrmypdf = cheap triage layer
- Mistral OCR API ≈ $130 — the option if Hindi retention becomes required

## 9. Next steps (agreed roadmap)

1. **Finish OCR** (§4) → clean rebuild → full-corpus embeddings
2. **MCP server** wrapping /api/search, /api/semantic, /api/chat, /api/document
3. **CBIC notifications ingestion** (core GST event feed; see notes deep-dive)
4. **Impact-matching layer**: business profiles (HSN/state) → rule facts → alerts
5. Embeddings note: open-india-law's published Qdrant vectors are voyage-4 — a
   different space; ours (nomic) are self-contained, which is fine by design.
