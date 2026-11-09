# GST Law Corpus — Design (gst-aar extension)

Date: 2026-09-06. Status: approved for spec → implementation plan.
Audience: business users AND CAs/consultants (both equally). One corpus, two UX surfaces (simple + expert).

## 1. Goal

Extend `gst-aar/` (2,888 AAR/AAAR rulings, SQLite FTS5 + vectors, Next.js chat on :3210)
into a comprehensive, searchable, chat-available GST database on the local laptop,
then keep it fresh with a daily checker. $0 local stack: SQLite, LM Studio
(`ornith-1.5-35b-a3b` LLM, `text-embedding-nomic-embed-text-v1.5` 768-d), macOS Vision OCR.

## 2. Hard constraints

1. **`.gov.in` sources only.** Every ingested document must come from a `.gov.in`
   host and carry its original publisher URL (`pdf_url` / `source_url`). No source
   URL → no downstream processing (standing provenance rule, `notes/official-sources.md`).
2. **Local laptop.** All work under `gst-aar/data/law/`; DBs regenerable via script;
   PDFs/texts gitignored. Check `df -h /System/Volumes/Data` before bulk steps —
   disk was at ~6.5 GiB free on 2026-09-06. PoC first on a small slice.
3. **Official publishers only, gov work basis.** Copyright Act 1957 s.17(d) government
   work, reproduction under s.52(1)(q); CC BY-style attribution everywhere; display
   the official link, never become the citation of record.
4. **No full DB wipes in routine operation.** `build_db.py` deletes `aar.db`; the new
   law pipeline must support incremental upserts so the daily checker never rebuilds
   embeddings from scratch.

## 3. Source map (.gov.in only)

| Stream | Layer | Source (all .gov.in) | Access pattern |
|---|---|---|---|
| A | Acts: CGST/IGST/UTGST/Cess 2017, 101st Amdt; Rules: CGST/IGST/UTGST/Cess rules, chapters, sections, forms; amendment histories | `taxinformation.cbic.gov.in` JSON API: `/api/authenticate-token` (anon JWT) → `/api/cbic-act-msts`, `-chapter-`, `-section-` (769 sections), `/api/cbic-rule-msts/-chapter-/-section-`, `/api/cbic-regulation-*`, `/api/cbic-amendment-doc-histories`, `/api/cbic-form-msts/download/{id}` (base64 PDF) | Paged GET harvest → raw JSON + decoded PDFs/HTML under `data/law/acts/`, `data/law/rules/` |
| B | Notifications (Central/Integrated/UT/Cess, rate + non-rate), circulars (CGST/IGST/Cess), instructions/guidelines, Removal-of-Difficulty + exemption orders, forms PDFs | `cbic-gst.gov.in` flat pages (`gst-acts.html`, `*-notifications.html`, `circulars.html`, `pdf/*.pdf`) + `www.cbic.gov.in/resources/htdocs-cbec/...` for customs/excise overlap | Flat-HTML crawl → PDF download log → Vision OCR; switch listing source to new-portal API only if its 500s recover |
| C | Council recommendations; Gazette bills→Acts + commencement dates; GSTN advisories/manuals/FAQs | `gstcouncil.gov.in`, `egazette.gov.in`, `services.gst.gov.in` | Targeted crawl (meeting-wise + year-wise); gazette match by title+number+date (no persistent cross-stage ID exists) |
| D | Rulings top-up: NAA anti-profiteering orders (s.171) | CBIC/DoR `.gov.in` NAA pages | Reuse AAR pipeline (`scrape_list` → download → Vision → `aar.db` pattern) |
| E | Litigation (roadmap, .gov.in only) | `cestat.gov.in` (GST-era) | Case-index first; reasoned-decision subset only. HC/SC AWS dumps are NOT .gov.in → excluded under this constraint |

IndiaCode (`indiacode.gov.in` variant) is a fallback mirror for cross-checking act text only;
CBIC is the source of record for GST because it carries section HTML + amendment history.

## 4. Architecture

```
.gov.in harvesters (A/B/C/D, independent, resumable)
  → data/law/raw/{acts,rules,notifications,circulars,council,gazette} + download_log.jsonl
  → parse: pymupdf4llm (text layer) / Vision OCR (scans) — reuse gst-aar extractors
  → structure: legal_section_detector + legal_chunker (repo scripts/pipeline/)
  → enrich: notification no/date/category, section/HSN/SAC citations, effective dates,
            rule facts (rate/threshold/deadline), plain-English summary
  → store: law.db (sqlite: documents, sections, notifications, rule_facts + FTS5)
           + vectors (LM Studio nomic, chunk-level, resumable)
  → serve: extend webapp /api/search, /api/semantic, /api/chat, /api/document
           + new /api/law (section lookup), /api/insights (ontology SQL queries)
  → daily checker (roadmap §7): diff → ingest → notify
```

Four harvest streams run in parallel (no shared state except `data/law/` + inventory).
Integration (DB + chat grounding) lands after each stream's first slice verifies.

## 5. Components

- `gst-aar/law/__init__.py` + `harvest_cbic_api.py` (Stream A: JWT, paging, base64 decode, amendment histories).
- `harvest_cbic_flat.py` (Stream B: flat-page crawl, `pdf/*.pdf` download, category/year parse).
- `harvest_council_gazette.py` (Stream C: meeting/year crawls, gazette bill↔act matcher).
- `law_db.py` (builds `data/law/law.db`: `documents`, `sections`, `notifications`, `rule_facts`, FTS5; incremental upsert by content-hash + source_url key).
- `law_search.py` (CLI parity with `search.py`: BM25 + section/citation filters).
- `webapp` extensions: law-first retrieval (statute → circular → ruling → litigation),
  dual UX (business: rate/what-applies; expert: full citation chain with official links).
- `check_daily.py` (roadmap §7).

## 6. Data flow and storage

- Raw: `gst-aar/data/law/{acts,rules,notifications,circulars,instructions,orders,forms,council,gazette}/`
  plus `download_log.jsonl` (source_url → local_path → sha256 → timestamp) and
  `inventory.csv|.jsonl` (parity with AAR inventory rule).
- Text: `gst-aar/data/law/text/...` + per-PDF status jsonl (append mode, resumable like Vision OCR).
- DB: `gst-aar/data/law/law.db` (gitignored, regenerable). Keep `aar.db` untouched;
  join at query time on (HSN/SAC, section, notification no) until a merge is justified.
- Vectors: chunk tables with `embedded` flag; `embed_law.py` resumes on unembedded chunks.

## 7. Daily checker (roadmap, part of this spec)

- `check_daily.py` + macOS `launchd` daily job (09:00 IST): re-fetch listing pages/APIs
  (A/B/C), compare by (source_url, sha256, `amendDt`/publish date), download only new/changed PDFs.
- Pipeline per new doc: OCR → chunk → enrich → upsert → embed new chunks → append
  `inventory` + `changes.jsonl` (date, type, no, subject, effective date, links).
- Output: `/api/changes?since=` + webapp "What's new" section + digest (email/Slack later;
  log file first). Never full-rebuilds; disk guard aborts below 10 GiB free.
- Success bar: new CBIC notification visible in search + chat citations within 24h of publish.

## 8. Error handling

- New-portal notification/circular APIs currently HTTP 500 server-side → Stream B uses
  flat PDFs now; retry API weekly and log status (do not block Stream A).
- WAF/TLS-fingerprint blocks on POSTs → GET APIs via httpx first; Playwright (real
  Chromium) only where GET fails; Indian-host/proxy via `.env` if geo-blocked.
- Scanned/image PDFs → Vision OCR; FTS5 hyphen quoting (`"e-invoicing"`); order-date
  sanity validation (1800–2100 range) per `fix_dates.py` pattern.
- Orphan-process guard: `ps aux | grep -E "extract|download|scrape|harvest|check_daily"`
  after any kill; status files are append-mode (delete for clean pass).

## 9. Testing and acceptance

- Provenance test: every DB row has a `.gov.in` source_url; zero rows without.
- Counts: acts == 15 API rows; sections ≈ 769; notifications/circulars match flat-page listings.
- Search sanity: `law_search.py "section 16 ITC"` returns CGST s.16; `"158/14/2021"` returns the circular; HSN query hits rule_facts.
- Chat grounding: statute-first answers with inline [n] citations to official PDFs.
- Daily checker dry-run: `--since 2026-09-01` produces a correct `changes.jsonl` with no DB wipe.

## 10. Build order (parallel where independent)

1. A-slice (5 acts + CGST rules, section DB + chat grounding) + B-slice (2024–2026 rate
   notifications) + C-slice (latest 4 Council meetings + matching gazettes) — in parallel.
2. Webapp law endpoints on top of whatever slices land first.
3. Full backfill 2017→2026 per stream.
4. NAA top-up + rule_facts/impact-matching.
5. Daily checker + `/api/changes` + "What's new" UI.
6. E-litigation (CESTAT) only after 1–5 are green.
