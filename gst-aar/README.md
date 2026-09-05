# GST AAR Pipeline — State & Handoff Notes

> **Restart-survival doc.** Everything needed to resume this work lives here.
> Last updated: 2026-09-05 (evening session).
> Parent context: [../notes/official-sources.md](../notes/official-sources.md)

> **Repo provenance:** this repository started as a clone of
> [Vaquill-AI/open-india-law](https://github.com/Vaquill-AI/open-india-law)
> (Apache-2.0 scripts, CC BY 4.0 data). Our own work lives in `gst-aar/` and
> `notes/`; upstream history was replaced by our private repo history.
> To sync upstream changes, re-clone that repo alongside and diff.

## Goal (priority 1, user-set)

Download all GST advance-ruling PDFs (AAR + AAAR orders) from
`https://www.gstcouncil.gov.in/authority-for-advance-ruling`, make them
machine-readable (text/OCR), and searchable in a **local** database.
**Current scope is a 25-PDF proof of concept** (user instruction: no bulk
downloads yet — a full run filled the disk).

## What the source looks like (verified 2026-09-05)

- Listing: `https://www.gstcouncil.gov.in/authority-for-advance-ruling?page=N`, N = 0..307
  (308 pages × ~10 rows ≈ **~3,080–4,300 rulings**, crawl got 2,111 unique URLs before dying)
- Table columns: `Sr. No. | Name of the Applicant | States/UT | Brief of Order | Order No. & Date | Download (PDF) | Category`
  (Category = section 97(2) clause(s))
- PDFs at `/sites/default/files/AAR/<file>.pdf` — plain GET, no auth, no WAF.
  **Most are scanned images with NO text layer** (0 chars via pymupdf) → OCR required.
- "Brief of Order" in the listing is a rich LLM-style summary already written by
  the site — excellent metadata, keep it in the DB.

## Pipeline scripts (this directory) — all plain stdlib + pymupdf + tesseract

| Script | What it does | State |
|---|---|---|
| `scrape_list.py` | Crawls listing pages → `data/aar_list.jsonl` (appends; resumable via start-page arg) | 2,111 records (pages 0–~214). **RESUME: `python3 scrape_list.py 213`** (dedupe by pdf_url happens in build_db) |
| `download_pdfs.py` | Downloads PDFs → `data/pdfs/<State>/<file>.pdf` (8 workers, resumable, validates %PDF magic) | **Paused per user: full run = ~2.4GB+ filled disk (99% full). PoC = 25 PDFs kept. Add throttling for future runs.** |
| `extract_text.py` | Native text via PyMuPDF; per-page tesseract OCR fallback (200dpi, psm 4, eng) → `data/text/<State>/*.txt` + `data/extract_status.jsonl` | ✅ Verified on 25-PDF PoC (tesseract engine; superseded by Vision below) |
| `extract_vision.py` | **Production OCR (benchmark winner): macOS Vision via PyObjC**, 150dpi render, 4 workers, resumable → `data/text/` + `data/extract_vision_status.jsonl`. Run: `ocr-benchmark/venv-tools/bin/python extract_vision.py`. Hindi dropped (accepted trade-off) | ✅ Smoke-tested, **awaiting user sign-off to launch on full corpus** |
| `build_db.py` | Builds `data/aar.db`: `rulings` table + `rulings_fts` (FTS5, porter tokenizer). All 2,111 metadata rows + 25 full-text bodies | **✅ VERIFIED — bugs fixed (see below)** |
| `search.py` | CLI search over the DB (FTS5 match + state/date filters + excerpts) | **✅ VERIFIED** — hyphenated queries quoted automatically |
| `export_inventory.py` | Exports `data/inventory.csv` + `data/inventory.jsonl`: one row per document with **original source URL**, local pdf path/size/download-time, text path, status | **✅ VERIFIED — 2,111 rows, 100% have source_url** |

## PoC data on disk right now

- `data/aar_list.jsonl` — 2,111 unique ruling records (~4,300 total exist)
- `data/pdfs/` — **exactly 25 PDFs across 20 states** (Andhra Pradesh…West Bengal)
- `data/text/` + `data/extract_status.jsonl` — OCR output for the 25 (626K chars)
- `data/aar.db` — **BUILT**: 2,111 rows, 25 with full text, FTS5 index live

## RUNNING NOW (started 2026-09-05 ~23:45, background task exec_d6a3ec51)

1. `scrape_list.py 213` — finishing the listing crawl (was 2,111; target ~4,300)
2. then `download_pdfs.py` — full corpus, **now throttled (0.5 s/req, 6 workers)**
   and writing every attempt live to `data/aar.db` table **`download_log`**
   (source_url → local_path → size → status → downloaded_at). Resumable.
3. After review: `ocr-benchmark/venv-tools/bin/python extract_vision.py` — macOS Vision OCR over all PDFs (the benchmark winner)
4. Then: rebuild `build_db.py` + `export_inventory.py` over the full corpus → embeddings → API/MCP layer (next phase)

Disk watch: corpus ≈ 6–7 GB; ~45 GB free at start. Check `df -h /System/Volumes/Data` if the run dies.

## Document inventory rule (standing, user-required)

**Every document ingested anywhere in this pipeline must be traceable to the
ORIGINAL publisher URL of its PDF.** This is maintained automatically:

- `data/rulings` table: `pdf_url` column (source of truth)
- `data/inventory.csv` / `data/inventory.jsonl`: full inventory export
  (`doc_key`, applicant, state, order no/date, **source_url**, local pdf path +
  size + download timestamp, text path + char count, status)
- Rebuild any time with `python3 export_inventory.py` (idempotent, reads the DB)
- Current coverage: 2,111/2,111 rows carry source_url; 25/25 local PDFs carry
  their URL, download timestamp, and text linkage.

Rule: **no document without a source URL ships downstream** (chunking,
embeddings, API responses). Future stages (CBIC, gazettes) must keep the same
columns when adding their own inventory rows.

## PoC verification (run 2026-09-05, all passing)

```
python3 build_db.py
python3 search.py "hsn" --limit 3                      # metadata+brief search across 2,111 rows
python3 search.py "e-invoicing" --state Rajasthan      # found Allen Career Institute order
python3 search.py "notification 13/2020" --full --limit 1   # shows OCR'd body excerpt
python3 search.py --state Karnataka --date-from 2024-01-01  # metadata filters
```

## Bugs fixed during PoC (2026-09-05)

1. ~~`build_db.py` broken FTS trigger hack~~ → removed trigger; FTS populated directly
   (metadata row first with empty body, then per-doc UPDATE with OCR text)
2. ~~Binding count mismatch~~ (16 vs 15) → body removed from metadata tuple
3. ~~extract_status lookup key mismatch~~ → key is now `<StateDir>/<file>.pdf` built
   from pdf_url (same convention as extract_text.py output paths)
4. ~~find_text_file absolute-path bug~~ (`DATA/"text"/abs_path` discards prefix) →
   path built from `state_dir/name` convention
5. ~~hyphenated FTS queries crash~~ ("e-invoicing" parsed as column syntax) → each
   term wrapped in double quotes in search.py

## Disk situation (IMPORTANT)

- Mac data volume was **99% full** (865Gi/926Gi used) — the bulk download and
  the first crawl attempt died with `No space left on device`. The user's disk
  is generally full; **check `df -h /System/Volumes/Data` before any bulk step.**
- The 25-PDF PoC is ~50–80MB. Full corpus ≈ 6GB+ PDFs + OCR text. **Do NOT bulk
  download without explicit user go-ahead and free disk space.**

## Next steps after PoC verification

1. Finish the listing crawl (`python3 scrape_list.py 213`) — adds ~2,000 more records
2. Review `ocr-benchmark/REPORT.md` (subagent benchmark of tesseract variants,
   ocrmypdf, Surya, EasyOCR, PaddleOCR, macOS Vision) → pick production OCR
3. Ask user: disk strategy for full corpus (external disk / prune / cloud)
4. Bulk download (throttled, resumable) → bulk OCR → rebuild DB
5. Then: embeddings (voyage-4 to match published Qdrant snapshots), MCP + REST API layer
6. Enrichment pass: parse order_no/date (split_order_field exists), HSN codes,
   cited sections, rates → `rule_fact` tables (see notes/official-sources.md)

## Session-context breadcrumbs

- Repo root `/Users/vishalkumar/Downloads/qlaw` = clone of github.com/Vaquill-AI/open-india-law
  (Apache-2.0 scripts, CC BY 4.0 data). Reuse its chunking/embedding pipeline.
- Product vision: rules-as-code SaaS, business-user "am I affected?" impact
  matching via HSN/SAC + state profiles, alerts, MCP + REST API. GST-first.
- User preference: inventory every official source encountered in
  notes/official-sources.md; PoC-scale everything before bulk runs.
