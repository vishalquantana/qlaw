# What's Left — GST Law Corpus status

**Updated:** 2026-09-14 · **Branch:** `feat/gst-backfill` · supersedes the 2026-09-12 pass.

---

## 1. What changed in this pass

| Work | Result |
|---|---|
| **Andhra Pradesh harvester built** | `harvest_ap.py` — the one state with no harvester. **703 GST G.O.s** enumerated 2017-2026 and downloaded. |
| **All reachable state feeds re-run** | Assam +7 (→77), Haryana +9 (→39); the rest were already complete. |
| **CBIC central notifications/circulars** | **502 PDFs** pulled from the Hindi mirror (the biggest single gap). |
| **Ingest** | +895 docs → `law.db` now **6,695 documents**, 6,545 with body (97%). |
| **OCR of thin scans** | 107 more documents recovered via macOS Vision. |
| **Text fill for body-less rows** | 437 documents filled (CBIC rows landed with an empty body). |
| **FTS index repaired** | **1,883 documents were held but unsearchable** — `documents_fts` had drifted from `documents` (a bare `UPDATE documents.body` in an earlier ingest path and in `ocr_thin.py`). Re-synced; `"GST"` hits went 3,812 → 4,709. `ocr_thin.py` fixed so it cannot recur; `reindex_fts.py` added as the repair tool. |
| **Ontology pass-1** | 6,539 / 6,695 documents (97%). |
| **Freshness registry** | `check_sources.py` now covers **18 feeds** (was 2), re-run based, with blocked sources named. |
| **Marketing pages** | `coverage-svgmap.html` + `coverage-map.html` regenerated, AP added, counts read live from the DBs. The map generator no longer reads its boundary paths from `/tmp` (they now live in `india-paths.ts`), so it is actually regenerable after a reboot. |
| **CBIC statute hierarchy** | The whole layer, not the 7 sample rows: **3,077 documents** — 15 acts, 96 act chapters, 769 act sections, 96 rules, 125 rule chapters, 1,294 rule sections, 37 amendments, 217 regulations, 428 forms. Fixed the TLS chain (the host omits its Sectigo intermediate) and tagged 794 non-GST records so they stay out of GST answers. Section *headings* are now searchable; the section **text is not exposed by any endpoint** (7 probed) and remains a separate extraction problem. |

State files on disk: **4,924**. `law.db`: **9,772 documents**, 9,622 with body (98%).

---

## 2. What is still open

### Blocked on a live session or a human
| Item | State | Needs |
|---|---|---|
| eSCR Supreme Court GST judgments | 3 of 27 | `ddddocr` CAPTCHA session (`/tmp` venv does not survive reboot) |
| GSTAT orders | 4 notices | assisted CAPTCHA session |
| Bihar | 0 files | login-walled; e-Gazette fallback not built |
| **West Bengal** | 410 files, frozen | `comtax.wb.gov.in:443` TCP-closed from this egress — run `harvest_wb.py` from an Indian host |
| **Haryana** | 39 of ~82 | `haryanatax.gov.in` drops connections from this egress (`RemoteDisconnected`); retry later or from an Indian host |

### Capped by the source, not by us
- **Uttar Pradesh** 431: the remaining ~70 listed PDFs are 404 on `comtax.up.nic.in`.
- **CBIC** 502 held of 1,168 listed: 656 links are 404, 7 have unencoded spaces. Nothing further is fetchable.

### Whole layers still at zero
| Layer | Held | Next |
|---|---|---|
| SGST Acts (~31 states) | 0 | harvest via India Code |
| Rate master (HSN/SAC) | `rate_held` / `rate_proposed` empty on every row | build from the rate notifications |
| CBIC section **text** | hierarchy held (3,077), no section bodies | no API exposes it — needs HTML extraction or a different source |

### Enrichment
- **New documents have no chunks or vectors.** LM Studio is off, so `embed_law.py` cannot run. The 43,968 existing chunks are all embedded; the ~2,900 new documents are searchable by FTS but not semantically.
- AAR ontology: 1,973/2,888 subjects, 983/2,888 questions (LM Studio pass parked).
- `/api/insights` not built (depends on the rate master).

### Housekeeping
- 28+ commits unpushed; `feat/gst-law-corpus`, `feat/law-embed`, `feat/gst-backfill` unmerged.
- No `launchd` job installed — the freshness registry is runnable but not scheduled.
- Untracked: `docs/superpowers/`, `gst-aar/vision_watchdog.sh`, `.workbuddy-ai/`.

---

## 3. Next three

1. **Turn LM Studio on and embed** — the new state + CBIC documents are keyword-searchable only until then.
2. **Retry Haryana and run WB from an Indian host** — the only two state feeds that are incomplete for reasons a retry can fix.
3. **Build the rate master** from the rate notifications now that they are in — it is the largest remaining structural gap and `/api/insights` depends on it.
