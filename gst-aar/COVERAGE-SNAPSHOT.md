# GST law corpus — coverage snapshot

**Measured:** 2026-09-14 · **Branch:** `feat/gst-backfill` · all figures read live from the databases.

---

## 1. Headline

| Metric | Value |
|---|---:|
| Documents in `law.db` | **10,075** |
| … with extracted text | 9,924 (**98%**) |
| … searchable in the full-text index | 9,924 (**0 index drift**) |
| … carrying ontology rows (subjects/citations) | 10,805 |
| Citations extracted | 617,006 |
| **AAR/AAAR rulings** (`aar.db`) | **2,888** |
| **Documents across all layers** (incl. AAR) | **12,963** |
| States / UTs with material | **31 of 36** |
| State GST Acts held in full | **28 of 28 states** |
| Central Act sections with wording | **702 of 769** |
| HSN / SAC codes mapped to a rate | **1,085** |
| Vector chunks | 66,607 (**0 stale**) |
| Source PDFs held on disk | 5,410 |
| Disk used / free | 826 GiB / 44 GiB |

> **Excluded from the counts: 992 rows that repeat another document's text.** Where a
> State publishes one consolidated order covering many notifications, every
> notification row links to that same document. The corpus now holds the order once
> and records the other notifications as `notification_ref` citations on it, rather
> than counting the same text repeatedly. Those rows are tagged `duplicate-of:<id>`
> in `law_tags` — nothing was deleted. Regenerate the check with
> `python3 gst-aar/law/dedupe_documents.py --check`.

> Run `python3 gst-aar/law/status.py` for a live read of all of the above.

## 2. By layer

| Layer | Documents | Text | Status |
|---|---:|---:|---|
| State GST notifications | 6,350 | 98% | 15 own-feed + 14 via India Code + 2 blocked |
| **State GST Acts** | **75** | **100%** | **all 28 states held in full** (3 UTs too) |
| Central GST Acts, Rules and sections | 3,327 | 100% | CGST Rules complete; 702 of 769 sections worded |
| AAR / AAAR advance rulings | 2,888 | ~100% | complete |
| Central notifications & circulars | 476 | 99% | 502 pulled; rest 404 upstream |
| Judgments / notices / other | 104 | 100% | eSCR 3, GSTAT 4, rest samples |
| GST Council minutes & discussion papers | 59 | 100% | complete |
| Central GST Bills + Acts | 10 | 100% | complete |

**Also held, outside the document table:** the HSN/SAC rate reference — 1,821
published rate lines covering 1,085 codes (`rate_facts` / `rate_codes`), queryable
via `law_search.py --rate <code>` and `/api/rate`.

### State coverage, two ways

| Basis | States / UTs | Meaning |
|---|---:|---|
| Dedicated state feed | 15 | Harvested from the state's own portal — freshest |
| India Code | 14 | Held from the official repository; no dedicated feed yet |
| Portal blocked | 2 | West Bengal, Bihar — material held, portal unreachable |
| Nothing yet | 6 | UTs administering GST through central legislation |

The distinction matters and both maps now show it: green = own feed,
teal = India Code, red = blocked, grey = nothing.

## 3. State feeds

| State | Files | Documents | Mapped (approx.) | Status |
|---|---:|---:|---:|---|
| Telangana | 479 | 1,190 | ~660 rows | harvested |
| Maharashtra | 759 | 759 | ~840 | harvested |
| Andhra Pradesh | 703 | 703 | 703 | harvested |
| Odisha | 612 | 612 | 612 | harvested |
| Rajasthan | 587 | 587 | 587 | harvested |
| Gujarat | 565 | 565 | 939 records | harvested (GST/CESS subset) |
| Delhi | 475 | 475 | ~500 | harvested |
| Uttar Pradesh | 431 | 431 | ~500 | capped — rest 404 upstream |
| **West Bengal** | 410 | 410 | ~460 | **blocked** — host unreachable from this egress |
| Assam | 77 | 77 | 77 | harvested |
| Tamil Nadu | 68 | 68 | 71 | harvested |
| Karnataka | 55 | 55 | 57 | harvested |
| Chhattisgarh | 40 | 40 | 42 | harvested |
| **Haryana** | 40 | 39 | ~82 | **partially blocked** — host drops connections |
| Kerala | 20 | 20 | 20 | harvested |
| Punjab | 14 | 14 | no static listing | partial |
| **Bihar** | 0 | 0 | — | **blocked** — login-walled |

## 3b. State coverage vs India — **17 of 36**

India has **28 states + 8 union territories**. Coverage now splits into two
different questions, and they have different answers:

| | Notification feed | SGST Act |
|---|---:|---:|
| States (28) | 17 | **28 — all held in full** |
| Union territories (8) | 1 (Delhi) | 3 |
| **Total** | **17 of 36** | **31 of 36** |

- **Legislation is essentially complete.** Every one of the 28 states' State GST
  Acts is held with its full text, from India Code. The 5 union territories without
  one administer GST through central legislation or a neighbouring state's Act.
- **Notification feeds remain the gap.** 17 of 36 states/UTs have a dedicated feed
  harvested from the state's own portal. The other 19 are covered by India Code
  instead — a harvest is in progress — but a state's own feed is fresher.

**States with no dedicated notification feed (12):** Arunachal Pradesh, Goa,
Himachal Pradesh, Jharkhand, Madhya Pradesh, Manipur, Meghalaya, Mizoram,
Nagaland, Sikkim, Tripura, Uttarakhand.

**Union territories with no dedicated feed (7):** Andaman and Nicobar Islands,
Chandigarh, Dadra and Nagar Haveli and Daman and Diu, Jammu and Kashmir, Ladakh,
Lakshadweep, Puducherry.

> Note on the union territories: most have no separate GST notification stream —
> they follow central notifications, or their tax administration is run by a
> neighbouring state. The substantive gap was the **12 states**, and India Code
> carries notifications for all of them.

### Of the 19, which are actually reachable?

Probed 2026-09-14. Several are blocked only by a **missing TLS intermediate** —
the identical fix already applied for CBIC, not a dead end:

| State / UT | Host | State of play |
|---|---|---|
| Himachal Pradesh | `hptax.gov.in` | reachable; needs Sectigo **DV** R36 intermediate |
| Madhya Pradesh | `mptax.mp.gov.in` | reachable; needs GeoTrust EV RSA CA G2 intermediate |
| Chandigarh | `chandigarh.gov.in` | reachable; needs eMudhra EM DV TLS CA G2A-1 intermediate |
| Goa | `goa.gov.in` | portal responds 200 — needs its GST notification page located |
| Puducherry | `py.gov.in` | portal responds 200 — needs its GST notification page located |
| Ladakh | `ladakh.gov.in` | portal responds 200 — needs its GST notification page located |
| Sikkim | `sikkimtax.gov.in` | serves no certificate at all — needs investigation |
| Arunachal, Jharkhand, Manipur, Meghalaya, Mizoram, Nagaland, Tripura, Uttarakhand | state portals resolve | GST feed not yet located |
| A&N Islands, DNH & Daman and Diu, J&K, Lakshadweep | — | not yet probed |

### Also missing: the SGST Acts themselves

Every one of the 28 states has its own **State Goods and Services Tax Act**. The
corpus holds **0** of them. (`kind='act'` holds 5 *central* act metadata rows;
47 documents merely mention "SGST" in passing.) These are harvestable from India
Code — the same source the upstream Open India Law corpus already uses for state
legislation, which requires an Indian IP.

## 4. Searchability

| Path | Coverage |
|---|---|
| Keyword / full-text (FTS5) | **9,622 documents — every document with text is indexed** |
| Semantic (vector) | **4,356 documents** (43,968 chunks, all embedded) |
| — no vectors yet | **5,416 documents** — pending LM Studio |
| Ontology (subjects, citations, tags) | 9,512 documents |
| Tagged `non-GST` (kept out of GST answers) | 794 records |

> **The main current limitation:** LM Studio is off, so the ~5,400 documents added since the last embedding run are keyword-searchable only. Everything is *held and citable*; it just is not yet reachable by semantic search.

## 5. Known gaps

| Gap | Detail |
|---|---|
| SGST Acts | 0 of ~31 states |
| Rate master (HSN/SAC) | `rate_held` / `rate_proposed` empty on every row |
| CBIC section text | hierarchy held; no API exposes the bodies |
| eSCR / GSTAT | CAPTCHA-gated (3 and 4 records held) |
| Haryana, West Bengal, Bihar | 3 state feeds incomplete for host-side reasons |
| Embeddings | 5,416 documents awaiting LM Studio |

---

*Regenerate the marketing view: `python3 gst-aar/law/coverage_svgmap.py`. Per-feed detail: [`law/SOURCES.md`](law/SOURCES.md). Remaining work: [`WHATS-LEFT.md`](WHATS-LEFT.md).*
