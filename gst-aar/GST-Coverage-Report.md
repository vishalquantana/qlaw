# GST Law Corpus — Coverage Report: What We Hold vs the Universe

**Date:** 6 September 2026 · **Scope:** GST law of India, official sources only (`.gov.in` / `.nic.in`)
**Method:** every "HELD" figure below is measured against the local corpus on this date.
Figures marked *(est.)* are universe estimates, not measurements.

## Executive snapshot

| Layer of GST law | Universe | We hold | Coverage |
|---|---|---|---|
| AAR / AAAR rulings (advance rulings, all states) | ~2,900 published orders | **2,888 rulings, 2,887 full texts** | ✅ ~100% |
| Central GST Bills as introduced (with SORs + notes on clauses) | 5 (122nd Amdt 2014; CGST/IGST/UTGST/Cess 2017) | **5 PDFs, full text, embedded (189 chunks)** | ✅ 100% |
| Central Acts (CGST/IGST/UTGST/Cess + 101st Amdt) | 5 + amending Finance Acts | 5 metadata rows (section text pending) | 🔄 metadata only |
| Notifications (Central/Integrated/UT/Cess, rate + non-rate, 2017→2026) | low thousands *(est.)* | 0 | ❌ next |
| Circulars / instructions / orders | 200+ *(est.)* | 0 | ❌ next |
| HSN / SAC rate master (rate + exemption per code) | ~5,200 HSN codes *(est.)* | 0 (AAR-derived HSN tags only) | ❌ next |
| CGST / SGST Rules + Forms + GSTAT Procedure Rules 2025 | ~160 CGST Rules + state rules + 124 GSTAT rules | 0 | ❌ queued |
| SGST Acts (states/UTs) | ~31 *(est.)* | 0 | ❌ queued (via India Code) |
| State SGST Bills | ~31, uneven archives *(est.)* | 0 | ❌ queued (catalog-first) |
| GSTAT orders (Principal + 31 State Benches, live since 16 Feb 2026) | 1,250+ appeals filed week one; growing daily | 0 | ❌ priority feed |
| Supreme Court + High Court GST judgments | subset of eSCR reporter | 0 | ❌ queued |
| GST Council recommendations / meeting decisions | 50+ meetings *(est.)* | 0 | ❌ queued |
| Lok Sabha debates (Mar 2017 passage) + Select Committee report (122nd Bill) | handful of records | 0 | ❌ queued |
| CESTAT orders (customs/excise/service-tax overlap) | large, mostly pre-GST relevance | 0 | ❌ low priority |

## 1. The universe of GST law (what "complete" means)

1. **Constitutional basis** — 101st Amendment Act 2016 (ex-122nd Bill 2014), Art. 246A/269A/279A.
2. **Primary legislation** — CGST, IGST, UTGST, Compensation Cess Acts + yearly Finance-Act amendments.
3. **Subordinate legislation** — CGST Rules (~160), SGST Rules per state, GSTAT Procedure Rules 2025 (124 rules, G.S.R. 256(E)).
4. **Rate law** — rate + exemption notifications per HSN/SAC; Council recommendations behind them.
5. **Administrative guidance** — circulars, instructions, Removal-of-Difficulty orders, FAQs.
6. **Advance rulings** — AAR per state + AAAR benches; NAAAR appeals (now under GSTAT Principal Bench).
7. **Appellate case law** — GSTAT (Principal + 31 State Benches, operational 16 Feb 2026); CESTAT for adjacent taxes.
8. **Constitutional/writ case law** — Supreme Court + High Court GST judgments (2017→), via the official eSCR reporter.
9. **Legislative history** — Bills as introduced, Statements of Objects & Reasons, Select Committee report, Lok Sabha debates.

## 2. What we hold (measured 2026-09-06)

- **2,888 AAR/AAAR rulings** (`gstcouncil.gov.in`), 2,887 with extracted text (Vision OCR), 2,888 PDFs (8.6 GB), each carrying its original publisher URL. Full-text FTS5 + live in chat search.
- **2,312 AAR chunk embeddings** (nomic-embed-text-v1.5, 768-d, LM Studio, $0 local) — partial; full re-run queued.
- **Structured ontology over AARs**: subjects with normalized HSN/SAC, citations (notifications/sections/rules), sector tags; per-question outcomes pending LLM pass v2.
- **5 central GST Bills, full text + embedded**: 122nd Amendment Bill 2014 (No. 192/2014) + CGST/IGST/UTGST/Cess Bills 2017 (Nos. 57–60/2017), with SORs and notes on clauses, each dated (introduction date stored; newer filings rank first in retrieval).
- **199 law-corpus vectors** over 10 documents (5 Bills + 5 Act metadata rows), BM25 + cosine verified.
- **Serving layer**: keyword search, semantic search, grounded RAG chatbot with inline citations to official PDFs; `/api/law` + `/api/changes` endpoints; daily freshness checker (dry-run).

## 3. Provenance & method (why this corpus is defensible)

- **Official sources only.** Every record traces to a `.gov.in` / `.nic.in` publisher and keeps its original publisher URL. No aggregators, no commercial reporters.
- **Recency precedence.** Every document carries its date; retrieval ranks best-match first, newest first on ties — newer filings and rules take precedence.
- **Fixed, citable artifacts.** Inventory + download log per document; no source URL, no downstream processing.
- **$0 local stack.** SQLite FTS5 + LM Studio embeddings/LLM + macOS Vision OCR. No cloud, no API spend.

## 4. Roadmap to full coverage (in priority order)

1. AAR embedding re-run to 100% (minutes) + `ruling_questions` LLM pass.
2. **GSTAT orders ingestion** (`gstat.gov.in` + e-filing portal) — the live case-law feed.
3. Notification/circular backfill 2017→2026 (listing-URL refresh first) + HSN/SAC rate master.
4. CGST Rules + Forms + SGST Acts (India Code reuse) + GSTAT Procedure Rules.
5. eSCR GST-judgment filter (SC + HCs) via Playwright (CAPTCHA-walled).
6. Council recommendations + debates/Select Committee report; state SGST Bills (catalog-first).
7. Wire the law corpus into chat (statute-first grounded answers) + `/api/insights`.
