# Source Method Records — how each feed is extracted & kept fresh

Living document: every harvest run updates its source's `last verified` line.
Goal from the user: **any state re-checked weekly/daily for what's new, then
extract → embed → serve, automatically.** The registry that does it is
`check_sources.py`; this file is the human-readable method behind each entry.

## Conventions (all sources)

- Official hosts only (`.gov.in` / `.nic.in`); every file keeps its publisher URL.
- Inventory: one JSONL row per file (`source_url → local_path → sha256 → date`).
- Pacing is per-host and adaptive — see **Politeness** below. `%PDF` validation,
  `--max N` PoC slices, resume by skipping seen URLs.
- TLS gotcha belt: several gov hosts omit intermediates — harvesters bundle
  `certs/` + certifi rather than disabling verification. Never `verify=False`.

## Politeness — `_throttle.py`

A flat 0.4s cadence is what got us blocked: `haryanatax.gov.in` answers a burst
with `RemoteDisconnected` and eSCR rate-limits by IP. Every harvester now calls
`_throttle` inside its `fetch()`/`_req()`, so **pacing is per request, in every
code path**, rather than a `sleep` bolted onto one loop.

| State | Gap between requests | Trigger |
|---|---|---|
| normal | **0.4s** (`LAW_MIN_DELAY`) | default |
| blocked | **300s** (`LAW_BLOCK_DELAY`) — one every 5 minutes | first blocking signal |
| ceiling | **1800s** (`LAW_MAX_DELAY`) | repeated blocking |

- **A blocking signal** is a connection reset / `RemoteDisconnected` / timeout, or
  HTTP 401/403/407/429/5xx. **A 404 or 410 is not a block** — dead links are
  normal in these listings and must not slow the run down.
- **Decay:** after 10 clean responses the gap halves back toward normal, so a host
  that recovers is not punished forever.
- **State persists** to `data/law/throttle.json`, so a host that blocked us in one
  run is approached gently in the next.
- **Inspect and adjust:**
  ```bash
  python3 gst-aar/law/_throttle.py --status          # which hosts pushed back
  python3 gst-aar/law/_throttle.py --relax           # all hosts back to normal
  python3 gst-aar/law/_throttle.py --set host=300    # pin one host
  python3 gst-aar/law/run_all_states.py --block-delay 300 --min-delay 5
  ```
  `LAW_THROTTLE_OFF=1` disables it (the tests use this).
- **What 5 minutes costs:** a feed with 400 files left needs ~33 hours at the
  blocked cadence. That is the point — but prefer running a blocking host
  overnight, or from an Indian IP, over lifting the ceiling.


## Telangana — Commercial Taxes Dept (`tgct.gov.in`)

- **Index pages** (GridView tables, plain GET, ~660 rows total Sep 2026):
  - Tax notifications: `/tgportal/GST/Uploads/bind_GST_NotificationsTax.aspx?type=Tax` (~434 rows: state G.O. no + CBIC no + dates + subject)
  - Rate notifications: `.../bind_GST_NotificationsRate.aspx?type=Rate` (~199 rows)
  - Circulars: `.../bind_GST_Circulars.aspx?type=Circulars` (~27 rows)
  - TGST Act text: `/tgportal/Docs/TelanganaGST_ACT.pdf` (direct, 1.6 MB)
- **Download mechanism:** per-row `__doPostBack` simulation. Session GETs the page,
  extracts `__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__EVENTVALIDATION`, POSTs with
  `__EVENTTARGET=<row control>`; response body IS the PDF. Chain fresh fields from
  each response. Two links per row: state G.O. (`lblCSTNoteNo`) + CBIC doc
  (`lblCibicNoteNo`) — harvest both.
- **Harvester:** `harvest_tgct.py`. Inventory: `data/law/staging/telangana/inventory.jsonl`.
- **Freshness:** re-GET the 3 index pages, diff row count/keys vs inventory, download only new.
- Last verified: 2026-09-06 (PoC 3 PDFs OK).

## CBIC central (`cbic-gst.gov.in`)

- **Listings:** English pages 404 since ~2026; **Hindi mirror live**:
  `hindi/central-tax-notifications.html`, `hindi/integrated-tax-notifications.html`,
  `hindi/circulars.html` (821 PDF links, `-Eng`/`-Hin` filename markers).
- **Download mechanism:** flat crawl, direct `pdf/*.pdf` links. Dead listings AND dead
  PDFs skip with a log line (never crash the run).
- **Harvester:** `harvest_cbic_flat.py` (`lang_hint()` tags en/hi). No inventory file —
  dedup key is `source_url` in `law.db`.
- Last verified: 2026-09-06 (PoC 3 PDFs via Hindi listings).

## CBIC API (`taxinformation.cbic.gov.in`)

- Anonymous JWT (`POST /api/authenticate-token` `{}`); notification/circular
  endpoints HTTP 500 server-side (use flat PDFs instead).
- **TLS:** the host serves a leaf issued by *Sectigo Public Server Authentication
  CA OV R36* and **omits the intermediate**, so plain urllib fails with
  `CERTIFICATE_VERIFY_FAILED`. The AIA URL is
  `http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt`; that
  certificate is in `certs/sectigo-ov-r36-intermediate.pem` and `_https.py`
  loads it. This was the "TLS-cafile fix" the design spec called for.
- **Endpoints (all return the full set in one response; page/size are ignored):**

  | Endpoint | Records | Stored as |
  |---|---:|---|
  | `cbic-act-msts` | 15 | `cbic_act` |
  | `cbic-act-chapter-msts` | 96 | `cbic_act_chapter` |
  | `cbic-act-section-msts` | 769 | `cbic_act_section` |
  | `cbic-rule-msts` | 96 | `cbic_rule` |
  | `cbic-rule-chapter-msts` | 125 | `cbic_rule_chapter` |
  | `cbic-rule-section-msts` | 1,294 | `cbic_rule_section` |
  | `cbic-amendment-doc-histories` | 37 | `cbic_amendment` |
  | `cbic-regulation-msts` | 583 | `cbic_regulation` |
  | `cbic-form-msts` | 437 | `cbic_form` |

- **No section text is reachable.** Section records carry `contentData: null` and
  only a `contentFilePath` (a `tax_repository/...html` path that 404s). Seven
  plausible content endpoints were probed on 2026-09-14 and all returned the SPA
  shell. So the harvest stores the **structured hierarchy** — number, heading,
  act, chapter, amendment date — which makes section *headings* searchable. The
  body remains a separate extraction problem.
- **Act scoping:** the repository holds 15 acts, only 10 of which are GST
  (CGST/IGST/UTGST, the J&K extensions, Compensation to States, the 101st
  Amendment, the 2023 amendments). Records belonging to the Customs, Central
  Excise, Customs Tariff, Provisional Collection and Finance Act Ch V acts are
  tagged `non-GST` in `law_tags`, which `/api/chat` already filters on.
- **Harvester:** `harvest_cbic_api.py` (`--full` for the whole layer, `--limit N`
  for the acts PoC). Last verified: 2026-09-14 — 3,077 documents.

## India Code (`indiacode.gov.in`) — the section text source

- **The site has migrated.** `indiacode.nic.in` now serves only a redirect page
  pointing at **`indiacode.gov.in`**. The old host was DSpace 5.5 (JSP, the
  `/SectionPageContent` AJAX API); the new one is **DSpace 7** with a REST API.
  **The scrapers in `scripts/legislation/` are stale** — they target endpoints
  that no longer exist.
- **Reachable with no geo-block.** The README's "India Code serves Indian traffic
  only" was true of the old host; the new one answers directly.
- **API** (no auth, no CAPTCHA):
  ```
  GET /server/api/discover/search/objects?scope=<collection>&query=<q>&size=100&page=N
  GET /server/api/core/items/{uuid}/bundles      -> ORIGINAL | TEXT | THUMBNAIL
  GET /server/api/core/bitstreams/{uuid}/content
  ```
  The **TEXT** bundle carries extracted text, so no OCR is needed for acts.
- **The CENTRAL community has a `Section` collection** (uuid
  `9a5b5f4a-4ccf-4cef-9820-0d33f8a6707f`, 35,368 items): one item per section of
  every central Act, carrying `dc.identifier.act_name`,
  `dc.identifier.section_number`, `dc.title` and the text in
  **`dc.identifier.section_page_note`**. Communities are one per state/UT plus
  CENTRAL, and each has collections: Acts, Section, Rule, Notification, Circular,
  Form, Schedule, Statute, …
- **Harvester:** `harvest_indiacode.py` → `data/law/indiacode/sections.jsonl`.
  **Join:** `join_cbic_section_text.py` matches on (normalised Act name,
  normalised section number) and writes the wording onto the CBIC section rows,
  keeping the CBIC URL as `source_url` and recording the India Code item URL in
  the body. Last verified: 2026-09-14 — 702 sections harvested, **678 joined**.

### State GST Acts and notifications

Each state/UT is a community with the **same collection layout as CENTRAL**
(Acts, Section, Notification, Circular, Rule, Form, Schedule, Statute, …), so one
harvester serves every state. Searching a state's `Acts` collection for
"Goods and Services Tax" returns its SGST Act, and the item's **TEXT** bundle
carries the full act text — no PDF, no OCR.

- **Harvester:** `harvest_indiacode_states.py` (`--only <state>` to target one,
  `--notifications` to also pull state GST notifications). Resumable: it skips
  any `source_url` already held under `sgst_act` / `sgst_notification`.
- Last verified: 2026-09-14 — the corpus went from **0 SGST Acts to full act text
  for the great majority of states**, e.g. Karnataka 621 KB, Goa 454 KB,
  Arunachal Pradesh 358 KB. The client report's "add the State GST Acts" item is
  therefore closed.


## CBIC GST rate schedule (`cbic-gst.gov.in`)

- **`gst-goods-services-rates.html` carries the published rate schedule.** Note
  the quirk: the **English page's tables are empty** (its CSS targets
  `#goods_table` / `#service_table`, but no rows are served). The **Hindi mirror**
  (`/hindi/gst-goods-services-rates.html`, ~875 KB vs 60 KB) has the data — the
  same pattern as the notification listings.
- Two tables:
  - `goods_table` — Schedules | S. No. | Chapter/Heading/Sub-heading |
    Description | CGST % | SGST/UTGST % | IGST % | Compensation Cess
  - `service_table` — S. No. | Chapter, Section or Heading | Description |
    CGST % | SGST/UTGST % | IGST % | Condition
- **`[Omitted]` rows are real data**, not a parse failure: withdrawn schedule
  lines are published with blank codes and rates and the literal text `[Omitted]`.
  They are kept, so "withdrawn" is distinguishable from "never listed".
- **Harvester:** `harvest_gst_rates.py` → `rate_facts` + `rate_codes` in law.db.
  `rate_facts` is one row per published schedule line (the source of record);
  `rate_codes` explodes the grouped code cells so a lookup by a single HSN/SAC
  works. Both tables are fully derived, so the script drops and rebuilds them.
  Last verified: 2026-09-14 — 1,821 facts (1,590 goods + 231 service),
  **1,085 distinct codes**.



## GST Council (`gstcouncil.gov.in`)

- Meeting page lists 59 PDFs (minutes books 1st–55th + discussion papers); flat crawl.
- **Harvester:** `harvest_council_minutes.py`. Inventory: `staging/council/inventory.json`.
- Last verified: 2026-09-06 (59/59 downloaded, ~1.1 GB).

## eSCR judgments (`scr.sci.gov.in`, `judgments.ecourts.gov.in`)

- Securimage CAPTCHA (6-char) per session; flow: index → image → `checkCaptcha` →
  home (WITH solved captcha) → DataTable POST (`ajax_req=true&app_token=`, `X-Requested-With`)
  → `openpdfcaptcha` (needs prior paging? no — direct call works, NO paging first,
  NO home-refetch with bogus captcha). `ddddocr` solves ~70% first-try (venv recipe in
  GST-SESSION-STATE.md). Sessions die ~15 min; IP rate-limits bite after heavy use.
- Full pull script: `staging/escr/pull-slow.py` (fresh session per PDF, 25s gaps).
- Status: 3/27 SC judgments held; resume pending.

## GSTAT orders (`gstat.gov.in`)

- Order search needs session CSRF + image CAPTCHA; `POST /get-documents` per doc-id.
  efiling login-walled. 4 notices held; full order pull needs assisted CAPTCHA session.

## West Bengal — Commercial Taxes (`comtax.wb.gov.in`)

- **Index:** single static table `GST/GST_Notifications/gst_notifications_state.html`
  (~460 rows 2017→2026, direct relative PDF links incl. `../GST_Acts_Rules/` bonus
  WBGST Act/Rules/ordinances).
- **Download mechanism:** flat crawl with relative-URL resolution. TLS: server needs
  unsafe legacy renegotiation → shared `_https.py` helper (never `verify=False`).
- **Harvester:** `harvest_wb.py`. Inventory: `staging/west-bengal/inventory.jsonl`.
- Last verified: 2026-09-06 (PoC 3 PDFs OK, incl. July-2026 notifications).

## Andhra Pradesh — G.O. repository (`goir.ap.gov.in`)

- **Index:** `goir.ap.gov.in` ASP.NET WebForms search. AP has no separate
  Commercial Taxes department in the repository: CTD notifications issue under
  **REVENUE**, so the search runs with `DDLDeptname=REV`.
- **Download mechanism:** POST the homepage with a `dd-mm-yyyy` date window, parse
  rows, then `dgo.ashx?gid=<gid>&fileType=E` **in the same session** — a bare GET
  returns 0 bytes. Row link is `javascript:downloadFile("<gid>","E")`.
- **Pagination workaround:** the result grid caps at 100 rows and its pager is an
  UpdatePanel postback that does not replay under plain urllib (clicking
  `Repeater1`/`rptPager` `lnkPage` returns page 1 again). Instead of paging we run
  **one narrow window per calendar year**, each of which stays under the cap.
- **Harvester:** `harvest_ap.py`. Inventory: `staging/andhra-pradesh/inventory.jsonl`.
- **Filter:** keeps rows whose abstract mentions GST/CGST/SGST/IGST, "goods and
  services tax", "value added tax" or APGST, which drops the large volume of CTD
  service matters (medical reimbursement, seniority, etc.).
- Last verified: 2026-09-12 (703 GST G.O.s enumerated 2017-2026; PDFs download OK).

## West Bengal — BLOCKED (network)

- `comtax.wb.gov.in:443` is **TCP-closed from the current egress** (verified
  2026-09-12). Not a parser failure and not a geo-block we can work around from
  here: the 410 files already held stay as they are.
- To refresh: run `harvest_wb.py` from an Indian host. Recorded here so the
  freshness registry reports it as blocked rather than silently green.

## State harvesters (all PoC-verified 2026-09-06/07 unless noted)

| State | Portal path | Mechanism | Rows/files mapped | Status |
|---|---|---|---|---|
| Haryana | haryanatax.gov.in LoadPartial (partial-view endpoint) | flat table, year buckets, dedupe (82 unique) | 503 rows / 82 files | PoC 5 |
| Gujarat | commercialtax.gujarat.gov.in circular.do Struts | cookie-jar + POST pagination, `urlOpenList1` download | 939 recs / 32pp | PoC 5 |
| Rajasthan | finance.rajasthan.gov.in GST postback section (NOT rajtax) | VIEWSTATE postback → ShowResult.aspx | 587-row table | PoC 5 |
| Delhi | Drupal table, ?page=0..24, key on /dvat/public-notice/ | flat + pager | ~500 rows | PoC 5 |
| Kerala | 2 static WP tables (KGST + State-Tax) | flat, entry-content scoped | 20 rows | PoC 5 |
| Karnataka | ASP.NET table, direct pdf hrefs | flat | 57 files | PoC 5 |
| Uttar Pradesh | hub → 10 year pages, EN+HI twins (quote spaces!) | flat crawl newest-first | ~500 files | PoC 5 |
| Tamil Nadu | FileOptionServlet JSON + DownloadServlet?fileId= | JSON API over JS page | 71 files | PoC 5 |
| Maharashtra | mahagst.gov.in ?page=N table (~70 rows/pg, 12+ pgs) | flat + pager | ~840 rows | PoC 9 |
| Assam | static bgcolor rows → ../GST/FORMATS/*.pdf | flat (slow files: curl fallback) | 77 files | PoC 5 |
| Bihar | Struts session+POST, needs RapidSSL cert | **BLOCKED**: "No Record Found" all variants — likely login-walled; alt: e-Gazette | — | blocked |
| Punjab | no static listing (JS-menu CMS) | substitutes: /attachments/*GST*.pdf updates | 5 files | partial |
| Chhattisgarh | Circ1 year-hub + GSTAT.htm (rich) | flat sweep, LE YR1 cert | 42 files | PoC 5 |

Shared TLS pattern: NIC/LE/Entrust hosts omit intermediates → `law/certs/*.pem` + `_https.py`
(strict verification kept). Full pulls next, in harvest order above.

## State portals (catalog: `staging/state-gst-portals.json`)

- Harvest order: West Bengal✅ → Odisha → Haryana → Gujarat → Delhi → Karnataka →
  Kerala → Assam → UP → TN → Rajasthan → (Punjab, Bihar, Telangana✅done, Chhattisgarh last).
- Maharashtra verified harvestable (`mahagst.gov.in`, `?page=N`, `/public/uploads/mvatservices/`).
- Each state gets a section here + a harvester (or a `check_sources.py` entry) as it lands.

## Pipeline order (after any harvest)

Run from the repo root with **`/opt/homebrew/bin/python3`** — it is the interpreter
that has `certifi` (needed by `_https.py`) and `fitz`.

```
1. harvest (per feed, or all at once)
   python3 gst-aar/law/run_all_states.py            # bounded concurrency, resumable
   python3 gst-aar/law/run_all_states.py --skip uttar-pradesh   # skip a feed whose
                                                    # remaining links are dead upstream

2. text
   python3 gst-aar/law/ingest_staging.py            # staging dirs -> law.db (fitz text)
   python3 gst-aar/law/fill_missing_text.py         # body='' rows -> extract from PDF
   <venv-tools>/python gst-aar/law/ocr_thin.py      # scanned PDFs -> macOS Vision OCR

3. statute text + rates (India Code / CBIC)
   python3 gst-aar/law/harvest_cbic_api.py --full        # hierarchy
   python3 gst-aar/law/harvest_indiacode.py              # section wording
   python3 gst-aar/law/join_cbic_section_text.py         # join on (act, section)
   python3 gst-aar/law/harvest_gst_rates.py              # HSN/SAC rate reference

4. dedupe (before quoting any count)
   python3 gst-aar/law/dedupe_documents.py --check
   python3 gst-aar/law/dedupe_documents.py               # tags, never deletes

5. index repair
   python3 gst-aar/law/reindex_fts.py

6. enrich
   python3 gst-aar/law/law_ontology.py --apply-pass1
   python3 gst-aar/law/embed_law.py                      # needs LM Studio

7. advertise
   python3 gst-aar/law/coverage_svgmap.py
   python3 gst-aar/law/coverage_map.py
   python3 gst-aar/reports/build_report.py               # client PDF
```

### Gotchas that have bitten

- **FTS drift.** Writing `documents.body` with a bare `UPDATE` leaves
  `documents_fts` holding the old (often empty) row, so the document is held but
  unsearchable. Always write through `law_db.upsert_document`, and run
  `reindex_fts.py` after any bulk text fill. 1,883 documents were silently
  unsearchable until this was caught on 2026-09-14.
- **Egress.** Traffic goes through a sandbox proxy that returns intermittent
  tunnel errors. Harvesters retry; the driver re-runs a feed that printed
  `index dead` (a silent failure that still exits 0).
- **pytest needs a writable TMPDIR** in the sandbox:
  `TMPDIR=$PWD/.pytest-tmp python3 -m pytest tests/ -q`.
- **Dead links are normal.** UP, CBIC and others carry 404s in their listings.
  `check_sources.py` subtracts URLs already logged as dead so "new" stays
  actionable.

