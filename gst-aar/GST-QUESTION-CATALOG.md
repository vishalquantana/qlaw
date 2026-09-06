# GST Question Catalog — what users ask, how we answer (with traces)

**Date:** 2026-09-06 · Every example below verified live against the corpus.
**Answer contract:** each claim carries `[doc kind + number, date, section/chunk]` and the
official `source_url`. Newer filings take precedence (retrieval: rank, then `pub_date DESC`).
Non-GST matches (e.g. 2025INSC946, an income-tax case) are tagged `non-GST` and never cited
for GST propositions.

## A. Business users ("what applies to me")

| # | Question | Answered from | Trace |
|---|---|---|---|
| B1 | When was GSTR-3B due for Oct 2024 in Maharashtra? | NN 26/2024-CT, 2024-11-18, operative para | [notification 26/2024-CT · `cbic-gst.gov.in/aces/Documents/…`] |
| B2 | I filed GSTR-9 but not 9C — is late fee due? | Cir 246/03/2025 §3.2–3.3 (s.47): return incomplete without 9C where required; FY≤22-23 excess waived if 9C by 31-03-2025 | [circular 246/03/2025 · 2025-01-30] |
| B3 | Do I need DIN on a portal-generated notice? | Cir 249/06/2025 §5: RFN-bearing communications need no DIN | [circular 249/06/2025 · 2025-06-09] |
| B4 | What HSN applies + what rate? | `law_citations` hsn_sac → rate notifications (rate master under build) + AAR `ruling_subjects.rate_held` | [ontology join, newest first] |
| B5 | I have till when to appeal to GSTAT? | GSTAT due-date notification 30-06-2026: pre-1-May-2026 orders → 31-07-2026 | [gstat_notice · 2026-06-30] |

**Answering strategy (business):** HSN/subject lookup → newest notification/circular →
one-line holding + effective date + official link. No case citations unless asked.

## B. Legal users ("what is the position")

| # | Question | Answered from | Trace |
|---|---|---|---|
| L1 | Can a s.83 attachment be renewed after a year? | 2025INSC983 §§39–42: lapses by operation of law; no renewal/re-issuance; accounts de-frozen | [judgment 2025INSC983 · 2025-08-14 · eSCR] |
| L2 | Do s.70 summons bar parallel proceedings? | 2025INSC982 §§96–97: summons/search ≠ 'proceedings' under s.6(2)(b); bar triggers on SCN; first-to-act carries inquiry; guidelines (a)–(i) | [judgment 2025INSC982 · 2025-08-14 · eSCR] |
| L3 | Who adjudicates multi-noticee DGGI show causes? | Cir 239/33/2024 §7.1 + 23-zone table; NN 31/2024-CT appoints officers | [circular + notification chain] |
| L4 | s.128A waiver where demand spans pre/post Mar-2020? | NN 11/2025-CT (Rule 164) + Instruction 02/2025-GST (dept-appeal cases) | [notification + instruction chain] |
| L5 | Review/revision/appeal against CAA orders? | Cir 250/07/2025 §4(a)–(e) under ss.107/108 | [circular 250/07/2025 · 2025-06-24] |

**Answering strategy (legal):** statute → circular → ruling → judgment chain, newest
authority last and controlling; conflicting AARs flagged for NAAAR/GSTAT resolution.

## C. Deliberation questions ("why is the law this way" — client's Council-minutes use case)

| # | Question | Answered from |
|---|---|---|
| D1 | Why 5% without ITC for restaurants? | Council minutes books (55 books held) — search deliberation chunks, cite meeting no. + date |
| D2 | What rate arithmetic did the CEA propose? | CEA RNR report (held) |
| D3 | What did Government tell itself about compensation? | DoR comments (2010) → 122nd Bill → Compensation Bill chain |

**Answering strategy (deliberation):** minutes are intent evidence, not law — always
paired with the enacted notification/section they led to; meeting number + date cited.

## Traceability contract (chat implementation checklist)

1. Retrieve: BM25 + vectors, `ORDER BY rank, pub_date DESC`; exclude `non-GST` rows for GST queries.
2. Compose: holding → effective date → `[n]` citation per claim.
3. Render: source card per citation (title, number, date, official URL).
4. Warn: supersession (newer notification on same number exists), partial coverage
   (e.g. "3 of 27 SC judgments held"), non-GST exclusion.
