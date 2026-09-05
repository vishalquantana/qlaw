# Official Sources of Indian Law — Catalog for Ingestion Pipeline

> Living document. Started 2026-09-05. Goal: catalog every **official** source of
> Indian legislation, bills, gazettes, tribunal/regulator decisions and judgments
> that our pipeline will need to download → parse/OCR → chunk → embed → serve
> (RAG via MCP + REST API).

## Working method (standing instruction)

**Every official source we encounter gets captured and inventoried in this
catalog — and where no scraper exists, we build one as needed.** Inventorying a
source means, at minimum: URL, what it publishes, format (HTML/PDF/scan),
access notes (geo-block, JS, CAPTCHA, robots/terms), and whether an
open-india-law scraper already covers it. No source is "done" until it has both
an inventory row and a working scraper (or an explicit reuse decision).

**Document-level provenance (user-required):** every document ingested by any
pipeline must carry the **original publisher URL of its PDF** in the inventory
(see `gst-aar/README.md` → "Document inventory rule"). No source URL, no
downstream processing.

## Ground rules

1. **Official sources only.** Every record must trace to a court, tribunal,
   legislature, gazette or government publisher. No commercial reporters
   (EBC/SCC), no aggregators (Indian Kanoon, PRS) as *sources* — PRS and similar
   are treated as mirrors/alerting aids only. (Same policy as `open-india-law`
   `coverage.yml`: `gov_only_sources: true`.)
2. **Provenance on every record.** Each chunk/section keeps its `source_url`
   pointing at the official PDF/page it came from. Products display the official
   link; we never become the citation of record.
3. **Copyright basis:** Government work under s.17(d), reproduction permitted via
   Copyright Act 1957 s.52(1)(q). Attribution is imposed by several sources'
   own terms (eCourts, NCLT/NCLAT policy) → CC BY-style attribution everywhere.
4. **Access realities to design for** (from `open-india-law` README + our probes):
   - India Code and several state portals **block/throttle non-Indian IPs**
     inconsistently → need Indian-hosted runner or `.env` proxy config.
   - Many portals are **JS SPAs** (indiacode.gov.in is Angular; plain HTTP GET
     returns an empty shell) → Playwright needed for some.
   - Some have **anti-bot** (CAPTCHA — scrapers reference capsolver/2captcha).
   - State gazettes are frequently **scanned PDFs** (e.g. Telangana gazette has
     Telugu + broken OCR text layer) → Mistral OCR fallback
     (`scripts/legislation/pipeline/ocr-mistral.py`).
   - Scrapers identify as `VaquillLegalBot/1.0` → we should use our own UA and
     respect per-source robots where possible.

---

## 1. Central legislation (Acts, Rules, Regulations)

| Source | What it publishes | URL | Notes |
|---|---|---|---|
| **India Code** (Legislative Dept., Ministry of Law & Justice) | Central Acts 1836→, all State/UT Acts, rules, regulations, ordinances; section-wise structure | `indiacode.nic.in` / `indiacode.gov.in` | DSpace backend; undocumented JSON API exists; robots disallows /discover, /simple-search; geo-blocks non-IN IPs intermittently; Angular SPA. **This is the backbone for legislation.** |
| **Gazette of India** | Bills as introduced, Acts as enacted, ordinances, notifications, rules | `egazette.gov.in` | The authoritative record of *what happened when*. Needed for bill→act lifecycle + effective dates. |
| **Ministry/department sites** | Sector-specific rules, notifications (e.g. `financialservices.gov.in`, `dopt.gov.in`) | varies | Secondary; each has its own layout. |

**Bill lifecycle note (verified via Telangana example, 2026-09-05):** a bill
exists first as a Gazette "Part IV-A Extraordinary" publication, then as an Act
(numbered within the year, e.g. Bill 9/2026 → Act 6..17/2026 family), then in
India Code. **No persistent identifier links these stages** — matching them is
an enrichment job for our pipeline (title + gazette number + date).

## 2. State legislation & gazettes (36 jurisdictions)

Pattern per state — need one gazette portal + one law-dept/legislature site each:

| State (example verified) | Gazette portal | Law Dept / Legislature | Notes |
|---|---|---|---|
| Telangana | `tggazette.cgg.gov.in` (searchable, doc IDs not guessable) | `law.telangana.gov.in` (`fileShow?fileName=/Uploads/LawDepartment/pdfNew/N of YYYY.pdf`) | Scanned PDFs w/ Telugu; OCR required |
| *(all others)* | TODO: catalog each | TODO | India Code already covers enacted state Acts; gazettes add bills + commencement notifications |

**Open India Law already holds 22,265 enactments / 1,098,577 sections from India
Code** (`scripts/legislation/indiacode-scraper.ts`) — we should reuse, not
re-scrape, and only add what it lacks: bills, gazette notifications, effective
dates, amendment chains.

## 3. Parliament

| Source | What | URL |
|---|---|---|
| Lok Sabha (Secretariat) | Debates, bills, questions | `loksabha.nic.in` |
| Rajya Sabha | Debates, bills | `rajyasabha.nic.in` |
| Law Commission of India | Reports (consultation + final) | `lawcommissionofindia.nic.in` |
| eGazette (see above) | Bills/Acts as introduced/enacted | `egazette.gov.in` |

Scraper exists: `scripts/parliament/download-lok-sabha-debates.py`.

## 4. Tribunals (decisions — the highest-value tier for business users)

All PDF-first; ~16% of documents are reasoned decisions. Schema per forum in
`scripts/tribunals/schema/`.

| Forum | Official URL | GST-relevant? |
|---|---|---|
| GST AAR / AAAR (per state) | state portals; scraper: `scripts/tribunals/gst-aar-scraper.ts` | **Yes — richest schema: hsn_sac_code, gst_rate, supply_type, question_of_law** |
| CESTAT (customs/excise/service tax) | `cestat.gov.in` | **Yes** |
| ITAT (income tax) | `itat.gov.in` | Tax-adjacent |
| CAT (central administrative) | `cgat.gov.in`, `cis.cgat.gov.in`, `catjudgements.nic.in` | — |
| DRT / DRAT (debt recovery) | `drt.gov.in`, `cis.drt.gov.in` | Finance |
| NCLT / NCLAT (company law, IBC) | `nclt.gov.in`, `efiling.nclt.gov.in`, `nclat.nic.in` | Corporate/IBC |
| NGT (environment) | `greentribunal.gov.in` | — |
| SAT (securities appellate) | `sat.gov.in`, `satweb.sat.gov.in` | Capital markets |
| APTEL (electricity) | `aptel.gov.in` | Energy |
| TDSAT (telecom) | `tdsat.gov.in` | Telecom |
| CCI (competition) | `cci.gov.in` | Competition |
| IBBI (insolvency regulator orders) | `ibbi.gov.in` | IBC |
| ATFP (forfeited property) | `atfp.gov.in` | — |
| RERA (per state) | `maharera.maharashtra.gov.in`, `erera.co.in` (Delhi), `rera.punjab.gov.in` | Real estate |

## 5. Regulators (subordinate legislation + orders/notices/circulars)

These publish the **orders and notices** business users care about most
(highest-frequency compliance events).

| Body | Official URL | Publishes |
|---|---|---|
| RBI | `rbi.org.in`, `rbidocs.rbi.org.in` | Notifications, master directions, circulars |
| SEBI | `sebi.gov.in` | Regulations, circulars, orders |
| MCA | `mca.gov.in` | Companies Act rules, notifications |
| CBIC (GST/Central excise/customs) | `taxinformation.cbic.gov.in` | **Notifications, circulars, orders — core GST feed. See deep-dive below.** |
| GST Council | `gstcouncil.gov.in` | Rate recommendations/changes |
| DGFT (foreign trade) | `dgft.gov.in`, `content.dgft.gov.in` | Policy circulars, FTP |
| TRAI | `trai.gov.in` | Regulations, consultations |
| IRDAI | `irdai.gov.in` | Regulations, circulars (robots.txt disallows all — deliberate s.52(1)(q) call documented upstream) |
| CPCB / MOEFCC | `cpcb.nic.in`, `moef.gov.in`, `parivesh.nic.in`, `environmentclearance.nic.in` | Directions, notifications |
| DFS (financial services) | `financialservices.gov.in` | Schemes, notifications |
| Income Tax Dept | `incometaxindia.gov.in` | Circulars, notifications, treaties |

## 6. Court judgments

- Supreme Court + 25 High Courts: already published under CC BY 4.0 on **AWS
  Open Data Registry** (Dattam Labs) — don't re-scrape; embed from there.
  Reader: `scripts/pipeline/aws-hc-parquet-reader.py`.
- eCourts / NJDG: `njdg.ecourts.gov.in`, `thc.nic.in` (district courts — out of
  scope v1, but the eventual "is there litigation on this issue?" layer).
- Qdrant embeddings for 32.5M chunks are already published (voyage-4, 1024-d) —
  we can skip re-embedding the base corpus entirely and only embed *new*
  documents our own ingestion adds.

---

## Deep dive: CBIC portals (recon 2026-09-05)

### A. New portal — `taxinformation.cbic.gov.in` (Angular SPA over JHipster/Spring Boot)

**Auth:** `POST /api/authenticate-token` with `{}` → anonymous JWT (`ROLE_ANONYMOUS`).
Send as `Authorization: Bearer <token>`. Token is enough for most GET APIs.

**Taxonomy** (`GET /api/cbic-tax-msts`): GST=1000001, Customs=1000002, Central
Excise=1000003, Service Tax=1000004, HSNS Cess=100005.

**Working, anonymous GET endpoints** (verified 2026-09-05):

| Endpoint | Returns |
|---|---|
| `/api/cbic-act-msts` | 15 Acts (CGST, IGST, UTGST, CGST/IGST J&K ext., Compensation Cess Act, Customs Act 1962, Customs Tariff 1975, Central Excise 1944, Finance Act Ch. V 1994, Constitution 101st Amdt…) with `issueDt`, `amendDt`, `contentFilePath` (PDF), `contentHtmlFilePath` |
| `/api/cbic-act-chapter-msts` | chapters per act |
| `/api/cbic-act-section-msts?page&size` | 769 sections: `sectionNo`, `sectionName`, `issueDt`, `amendDt`, HTML file path |
| `/api/cbic-rule-msts`, `-chapter-`, `-section-` | rules hierarchy |
| `/api/cbic-regulation-msts`, `-chapter-`, `-doc-` | regulations |
| `/api/cbic-notification-msts` etc. | listings (see below — currently failing) |
| `/api/cbic-amendment-doc-histories` | **amendment history — key for rules-as-code effective dates** |
| `/api/cbic-attachment-dtls` | attachment metadata (`docFilePath`) |
| `/api/cbic-form-msts/download/{id}` | **file download as base64 JSON** (`{"data":"JVBERi..."}` = PDF); variants `/download/{id}/{language}` and per-entity (`ruleId`, `serviceTaxMstId`) |
| `/api/cbic-content-maps/content-dtls` (POST) | content listings by `{taxId, contentType, contentId}` — **WAF-blocked from curl** |

**Custom query endpoints** (GET, from bundle): `fetchNotificationByYearAndCategory`,
`fetchNotificationByYear`, `fetchNotificationHistory`, `fetchCircularByYearCategory`,
`fetchCircularHistory`, `fetchLatestUpdatesbyTaxId`, `viewAllSectionByActId`,
`fetchRules`, `fetchRegulations`, `fetchForms`… (params: `year`, `page`, `size`,
`taxId`, `category`, `keyword`/`searchKeyword`).

**Current state / problems:**
1. **Notification & circular listing endpoints return HTTP 500 (CoreException)**
   — tested from curl AND from inside the live browser session. The portal's
   backend data access is broken/flaky server-side right now. Acts/rules/sections
   endpoints work fine. → Build the legislation harvest on the working endpoints;
   monitor the failing ones; fall back to old portal for notifications meanwhile.
2. **WAF** (F5/BIG-IP "Request Rejected") blocks non-browser POSTs to several
   `/api/...` endpoints regardless of browser-mimicking headers → likely TLS
   fingerprinting. If needed, scrape through Playwright (real Chromium) instead of httpx.
3. **Content files** live on an internal Windows-style path (`tax_repository\gst\acts\...`)
   not directly fetchable anonymously; the SPA either reads inline `contentData`
   or hits `/download/{id}` base64 endpoints. Needs one authenticated walk to map.
4. Elasticsearch `_search/*` endpoints: down ("Failure during data access").

**Portal UI structure** (for Playwright scraping if API stays broken): per tax
head menu → Acts / Rules / Forms / Notifications / Circulars / Instructions /
Orders. Notifications filterable by category (Central Tax, Central Tax (Rate),
Integrated Tax (Rate), UT Tax, Compensation Cess…) and year 2017–2026.

### B. Old portal — `cbic-gst.gov.in` (plain HTML, still updated in 2026)

Flat HTML pages with **direct `pdf/*.pdf` links** — much easier to scrape:
- `gst-acts.html` → CGST/IGST/UTGST Acts, all Rules (individual rule PDFs), bills
- homepage carries latest circulars, notifications (`NN-26-2024_Eng.pdf`),
  central excise notifications, HSNS advisories (dated 2026 — actively maintained)
- Hindi mirror under `hindi/`
- **Best near-term feed for GST notifications/circulars** while the new portal's
  API is broken. Customs/excise equivalents live on `www.cbic.gov.in/resources/htdocs-cbec/...`

### CBIC scraper plan
1. **Phase 1 (legislation):** harvest acts/chapters/sections + amendment histories
   from the new portal's working JSON APIs (anonymous JWT, page through, decode
   base64 downloads). Reuse repo's section-chunking pipeline.
2. **Phase 2 (events):** notifications/circulars/orders from `cbic-gst.gov.in`
   (flat PDFs, trivially scrapeable) + `www.cbic.gov.in` resources; switch to new
   portal API for history/backfill once its backend recovers.
3. **Enrichment:** notification number/date/category parse → link to cited
   sections/HSN codes → rule-fact extraction (rates, thresholds, effective dates).


   → raw PDFs/HTML  (S3-compatible store, content-hash dedup)
   → parse: pymupdf4llm (text layer) / Mistral OCR (scanned)
   → structure: legal_section_detector + legal_chunker (repo provides both)
   → enrich (LLM): rule facts (rate/threshold/deadline), HSN/SAC tags,
     cited sections, effective dates, bill↔act linkage, plain-English summary
   → store: Postgres (structured, per-forum schemas exist) + Qdrant (vectors)
   → serve: REST API + MCP server (search, get_rule, check_impact, changes_since)
   → alert: new doc → profile match (HSN/state/section recall) → LLM verify
     → digest (email/WhatsApp/Slack)
```

## Next steps / TODOs

- [ ] Catalog gazette + legislature URLs for all 36 state jurisdictions
- [x] Probe CBIC `taxinformation.cbic.gov.in` — full API map done (see deep-dive); notifications API currently 500s server-side
- [ ] Build CBIC Phase-1 scraper (acts/chapters/sections + amendment histories via JSON API)
- [ ] Build CBIC Phase-2 scraper (notifications/circulars from `cbic-gst.gov.in` flat PDFs)
- [ ] Map CBIC file-download flow (`/download/{id}` base64) for act/section documents
- [ ] Decide reuse boundary vs open-india-law corpus (reuse legislation + judgments; build bill/gazette + notifications ingestion ourselves)
- [ ] Design `business_profile`, `rule_fact`, `legal_event`, `impact` schemas
- [ ] Write MCP tool surface spec
- [ ] Check terms/robots for each new source we add (mirror `coverage.yml` discipline)
