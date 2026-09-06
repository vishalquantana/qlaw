# Source Method Records — how each feed is extracted & kept fresh

Living document: every harvest run updates its source's `last verified` line.
Goal from the user: **any state re-checked weekly/daily for what's new, then
extract → embed → serve, automatically.** The registry that does it is
`check_sources.py`; this file is the human-readable method behind each entry.

## Conventions (all sources)

- Official hosts only (`.gov.in` / `.nic.in`); every file keeps its publisher URL.
- Inventory: one JSONL row per file (`source_url → local_path → sha256 → date`).
- Throttle 0.4s, `%PDF` validation, `--max N` PoC slices, resume by skipping seen URLs.
- TLS gotcha belt: several gov hosts omit intermediates — harvesters bundle
  `certs/` + certifi rather than disabling verification. Never `verify=False`.

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

- Anonymous JWT (`POST /api/authenticate-token` `{}`); acts/rules/sections/amendments
  endpoints alive; notification/circular endpoints HTTP 500 server-side (use flat PDFs).
- **Harvester:** `harvest_cbic_api.py`. TLS needs AIA-completed bundle (server omits intermediate).
- Last verified: 2026-09-06 (5 acts PoC).

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
