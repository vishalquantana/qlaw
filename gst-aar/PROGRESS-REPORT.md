# Progress Report — GST Legal Assistant build
**Date:** 2026-09-06 · **Branch:** `feat/gst-backfill` · **Repo:** /Users/vishalkumar/Downloads/qlaw

## One-line status
**4,644 state-law files on disk, 1,135 in `law.db` with body + 5,929 total docs, 43,968 vector chunks, 1,442 ontology subjects across AARs + law corpus. AAR bulk-ontology (LM Studio jobs) paused; all LM-free work running in background.**

## What's in the corpus

| Layer | Held | Universe | Status |
|---|---|---|---|
| AAR/AAAR rulings | 2,888 (text + 28,575 chunks) | ~2,900 | 🟢 |
| Central GST Bills (as introduced) | 5/5 | 5 | 🟢 |
| Council minutes + papers | 59/59 | 59 | 🟢 |
| Central Acts (CBIC API) | 5 metadata + 769 sections + 160 rules + 37 amendments | full set | 🟡 metadata, pull queued |
| Central Notifications/Circulars (Hindi) | ~470 ingested | low 1,000s | 🟡 pulling |
| SC judgments (eSCR) | 3 | 27 found | 🟡 CAPTCHA-resume pending |
| GSTAT orders | 4 notices | many | 🔴 CAPTCHA-gated |
| State notifications | TG 479, WB 410, OD/MH/GJ/UP/RJ/DL/KA/KL/HR/TN/AS/CG full pulls running or done | varies | 🟡 in flight |
| Rate master (HSN/SAC) | 0 structured | ~5,200 | 🔴 build from notifications |
| SGST Acts (states) | 0 | ~31 | 🔴 via India Code |

## Parallel workers running now

1. **9 state harvesters** (KA, UP, TN, HR, RJ, DL, KL, AS, CG) — all resumed, idempotent
2. **OCR thin PDFs** (gst-aar/ocr-benchmark/venv-tools/bin/python gst-aar/law/ocr_thin.py) — local Vision, no LM Studio
3. **Ingest wave** (gst-aar/law/ingest_staging.py) — extracts text, upserts with dates, runs pass-1 ontology
4. **Embeddings** — waiting on LM Studio; will resume automatically when `/v1/models` comes back

## What was achieved this session (committed)
- 13 state harvesters + method records (`SOURCES.md`)
- Shared TLS helper (`_https.py`) for gov hosts missing intermediates
- 105 tests, 3 new TLS certificates
- Interactive India SVG coverage map (`coverage-svgmap.html`) — 37 states, hover tooltips
- Visual status dashboard (`status_dashboard.html`)
- 50-question stress set (`stress-50.txt`) + question catalog (`GST-QUESTION-CATALOG.md`)
- All-green coverage plan (`ALL-GREEN-PLAN.md`)
- Source method record (`SOURCES.md`) — every feed, every quirk, verified
- Chat hero with markdown answers, sources rail, local PDF preview
- Law-corpus retrieval wired into `/api/chat` (statute-first ordering, LLM retry, stopword fix)
- Ontology pass-1 applied to all law docs; semantic pass on 1,442 AARs by hand

---

# GREEN PLAN — minimum path to all green per feed

## Definition of green (per feed)
1. Harvester + fixture tests committed
2. Full pull completed in `staging/<feed>/inventory.jsonl` + PDFs
3. `ingest_staging.py` (text + dates + upsert) into `law.db`
4. Pass-1 ontology applied
5. `embed_law.py` vectors land (needs LM Studio)
6. Semantic ontology rows (manual for AARs, scripted for new feeds)
7. `check_sources.py` registry entry with cadence
8. `SOURCES.md` method record

## The 4 bottlenecks (in priority order)

### 1. State notifications full pull + ingest
**Status:** 9 harvesters in background, ~4,644 files in. After they finish:
```
python3 gst-aar/law/ingest_staging.py   # idempotent resume
python3 gst-aar/law/law_ontology.py --apply-pass1
nohup python3 gst-aar/law/embed_law.py &   # when LM Studio back
```
**Target time:** pulls 1–2h; ingest 10min; ontology 5min; embeddings 30min for ~3,000 new docs.

### 2. OCR the ~170 thin PDFs
- Currently running (macOS Vision, no LM Studio)
- **Blocker if files have only partial text** — flag and skip
- Then re-run ingest to fill bodies

### 3. Central CBIC full backfill (Hindi site)
- `harvest_cbic_flat.py` is pulling
- After done: ingest → embed
- Plus **CBIC rate master** — once notifications are in, structure as `rule_facts(HSN→rate, exemption_list)`

### 4. AAR ontology LLM pass v1 + v2 (questions)
- Parked since LM Studio off
- Resume: `python3 gst-aar/extract_ontology.py --llm` then `--llm-questions`
- Already 1,442 hand-done; remaining 1,446

## What to do right now (in order, LM-free where possible)

1. ✅ Launch state full pulls — **done, 9 running**
2. ✅ Launch OCR — **done, running**
3. ✅ Launch ingest + pass-1 ontology — **done, running**
4. **Wire law corpus into `/api/chat`** — I started this in route.js (statute-first order, LLM retry, stopword fix) and the wire-in is in place; need to verify end-to-end with the new law corpus
5. Once LM Studio returns: embeddings of all new state docs → AAR ontology v1 + v2

## Risks / open questions
- **eSCR CAPTCHA** still blocks the 24 remaining SC judgments + all HC judgments
- **GSTAT** still CAPTCHA-walled; needs assisted session
- **Bihar** still login-walled; e-Gazette is the fallback
- **Rate master** has no upstream feed yet (needs structured extraction from notifications — design work)

## End-state check (regenerable anytime)
```
python3 gst-aar/law/coverage_svgmap.py    # visual map
python3 gst-aar/law/status_dashboard.py    # cards + tables
```

## What we are NOT doing
- Re-pulling data we already hold (idempotent resumes prevent this)
- Waiting on LM Studio where we can OCR / regex / read ourselves
- Manual AAR ontology beyond what's been hand-extracted (1,442 done, 1,446 LM-paused)
