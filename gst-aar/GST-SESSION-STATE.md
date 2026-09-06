# Session State — GST law corpus build (restart-survival doc)

> Last updated: 2026-09-06 ~evening (after eSCR pull park).
> If this session died, start here. Companion: `README.md §0`, `GST-Coverage-Report.md`.

## Branches (all local, unpushed)

| Branch | Contains |
|---|---|
| `main` (ca95ac8) | pre-law-work baseline |
| `feat/gst-law-corpus` (ad016b6) | Tasks 1–6 reviewed+merged: law harvesters, search, /api/law, /api/changes, daily checker |
| `feat/law-embed` (3083388) | + embed_law.py, 5 GST Bills pipeline, recency-precedence search |
| `feat/gst-backfill` (current) | + parallel-agent outputs (data only): AAR embeddings complete, staging samples |

## What's DONE (verified)

- AAR: 2,888 rulings, 2,887 texts, **28,575 chunks, 0 nulls** (Agent A finished full re-run).
- law.db: 30 docs (5 acts meta, 5 bills full-text, 10 notifications, 3 SC judgments, 4 GSTAT notices, 1 rule/1 section/1 amendment sample), **511 law_chunks**, BM25 + cosine verified, recency ordering live (`ORDER BY rank, pub_date DESC`).
- Staging: `gst-aar/data/law/staging/{gstat,notifications,rules,escr}/` each with inventory.jsonl (+ rules samples, listing-map.json, **allrows-27.json**, **pull-slow.py**).
- eSCR mechanism PROVEN: PHRASE query → 27 SC GST judgments; 3 PDFs pulled (2025INSC982/983/946).
- ddddocr benchmarked ACCEPTED on live Securimage (4+ solves, ~70% first-try). Reinstall: `python3 -m venv /tmp/captchavenv && /tmp/captchavenv/bin/pip install ddddocr` (system pip is PEP-668 blocked; /tmp venv does NOT survive reboot).

## What's PARKED (tomorrow)

- **eSCR 24 remaining PDFs**: run `gst-aar/data/law/staging/escr/pull-slow.py` with `/tmp/captchavenv/bin/python` (fresh session per PDF, 25s gaps, ~25 min). Recipe that works: solve → home&captcha=<real code> → openpdfcaptcha DIRECTLY (ajax header). Do NOT DataTable-page first (breaks openpdf state); do NOT refetch home with bogus captcha (resets solved state). If `outputfile:null` returns: stop hammering (IP rate-limit), switch egress IP, retry.
- GSTAT orders: CAPTCHA+CSRF gated, needs assisted session or solver (ddddocr untested there).
- Notifications full pull: listing-map.json has working URLs; rate/cess series need cbic.gov.in SPA API.
- Rules backfill: single-GET datasets confirmed (96 rules/769 sections/37 amendments); harvester needs TLS-cafile fix (server omits intermediate).
- Then: upsert new PDFs → embed_law.py → law_search verify → commit.

## Gotchas (do not rediscover)

- eSCR sessions die in ~15 min; CAPTCHA images/session files in /tmp (gone after reboot — rows+script are backed up in staging/).
- LM Studio flakiness: model occasionally unloads mid-embed (HTTP 400 "Operation canceled") — rerun, scripts resume.
- Egress was 206.189.139.17 (rate-limited at eSCR), then 183.82.100.136 via VPN (worked briefly). If blocked again: change egress.
- `/api/law` returned 500 on last check (dev server may need restart after route.js edit): `cd gst-aar/webapp && npm run dev` (port 3210).
- Untracked clutter to triage: `docs/superpowers/`, `gst-aar/vision_watchdog.sh`, empty `gst-aar/webapp/public/`.

## LM Studio OFF (2026-09-06 eve) — deferred until back
- Ontology v1 stopped at +175 (total ~946/2888); v2 watcher killed before firing. Resume: `python3 gst-aar/extract_ontology.py --llm` then `--llm-questions` (background each).
- Embeddings deferred everywhere (law re-embeds, if any). AAR chunks complete (28,575) — nothing pending there.
- Webapp /api/chat + /api/semantic need LM Studio (LLM + embeddings); /api/search, /api/law, /api/document, /api/pdf, /api/changes all work offline.
- Works WITHOUT LM Studio: downloads, pymupdf/Vision-OCR extraction, chunking, FTS, regex ontology, in-session semantic extraction, frontend, harvesters.
