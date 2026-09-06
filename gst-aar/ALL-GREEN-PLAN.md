# ALL-GREEN Plan — full GST universe coverage

**Goal:** every layer below at green = harvested + extracted + embedded + searchable + fresh-checked.
**Date:** 2026-09-06 · Status counts measured same day.

## Per-state board (files on disk → green bar)

| State | Harvester | Files | Ingested | Fresh check | Bar |
|---|---|---|---|---|---|
| Telangana | harvest_tgct.py ✅ | 479 | ✅ 479 | check_sources weekly | 🟢 |
| West Bengal | harvest_wb.py ✅ | 410 | ✅ 410 | queued | 🟢 pull done |
| Odisha | harvest_od.py ✅ | pulling (~612 mapped) | queued | queued | 🟡 |
| Maharashtra | harvest_mh.py ✅ | pulling (~840 mapped) | queued | queued | 🟡 |
| Gujarat | harvest_gj.py ✅ | PoC 5/939 mapped | queued | queued | 🟡 |
| Rajasthan | harvest_rj.py ✅ (finance postback) | PoC 5 | queued | queued | 🟡 |
| Delhi | harvest_dl.py ✅ | PoC 5 | queued | queued | 🟡 |
| Kerala | harvest_kl.py ✅ | PoC 5 (20 rows total) | queued | queued | 🟡 |
| Karnataka | harvest_ka.py ✅ | PoC 5/57 | queued | queued | 🟡 |
| UP | harvest_up.py ✅ | PoC 5/~500 | queued | queued | 🟡 |
| Tamil Nadu | harvest_tn.py ✅ (JSON servlet) | PoC 5/71 | queued | queued | 🟡 |
| Assam | harvest_as.py ✅ | PoC 5/77 | queued | queued | 🟡 |
| Chhattisgarh | harvest_cg.py ✅ | PoC 5/42 | queued | queued | 🟡 |
| Punjab | harvest_pb.py ✅ (substitute updates) | PoC 5 | queued | queued | 🟡 |
| Andhra Pradesh | NEEDS harvester (goir.ap.gov.in dgo.ashx G.O.s; apct portal redesigned) | 0 | — | — | 🔴 next |
| Bihar | harvest_br.py (login-walled) → e-Gazette fallback | 0 | — | — | 🔴 blocked |

## Central layers board

| Layer | Status | Next |
|---|---|---|
| AAR rulings + embeddings | 🟢 2,888 / 28,575 chunks | ontology: me (142) + LM jobs parked |
| Central Bills | 🟢 5/5 full text + embedded | done |
| Council minutes + papers | 🟢 59/59 + embedded | 56th+ via check |
| Notifications/circulars (Hindi backfill) | 🟡 pulling (~600+, 1,126 mapped) | finish pull → ingest |
| CBIC Acts/Rules/Sections/Amendments | 🟡 metadata + samples | full API backfill |
| SGST Acts (India Code reuse) | 🔴 0 | harvest_indiacode_sgst |
| Rate master (HSN/SAC) | 🔴 tags only | build from notifications |
| GSTAT orders | 🔴 CAPTCHA-gated (4 notices) | assisted session |
| eSCR SC (24 left) + HC judgments | 🟡 3 held, pull-slow ready | resume post-block |
| Debates / Select Committee / NAAAR / CESTAT | 🔴 | queued in order |

## Definition of green (per feed)

1. Harvester + fixture tests committed; 2. full pull in staging + inventory;
3. ingest_staging (text + dates + upsert); 4. embed_law vectors; 5. ontology
pass-1 + semantic rows; 6. check_sources registry entry with cadence;
7. SOURCES.md method record. law.db is the merge point; vectors last (LM Studio).

## Execution order (background-friendly)

1. Let current pulls finish (OD, MH, Hindi, WB done) → ingest waves.
2. AP harvester (goir G.O. search) + SGST Acts via India Code.
3. Full pulls: GJ → UP → RJ → DL → KA → rest (each resumable, one at a time for disk).
4. eSCR resume (new egress) + GSTAT assisted CAPTCHA.
5. Rate master build; NAAAR/debates/CESTAT last.
