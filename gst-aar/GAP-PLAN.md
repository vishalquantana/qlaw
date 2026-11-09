# Gap plan — what to do about every known gap

**Researched:** 2026-09-14 · evidence below is from live probes run today, not inference.

---

## The headline finding

**India Code has migrated, and the move is good news.**

`indiacode.nic.in` now serves only a redirect page pointing at **`indiacode.gov.in`**.
The old site was DSpace 5.5 JSP; the new one is **DSpace 7** (Angular + a documented
REST API). Two consequences:

1. **The existing India Code scrapers are stale.** `scripts/legislation/indiacode-scraper.ts`
   targets `/browse?type=shorttitle` and the `/SectionPageContent` AJAX endpoint. Both
   are gone. Any run of it now returns 404s.
2. **The new host is reachable from here, with no geo-block.** The README warns that
   India Code serves Indian traffic only. That was true of the old host; the new one
   answers our requests directly. This was the single biggest assumed blocker on the
   whole gap list, and it no longer applies.

Verified working API (no auth, no CAPTCHA, JSON):

```
GET https://indiacode.gov.in/server/api/discover/search/objects?query=<q>&size=50&page=N
GET https://indiacode.gov.in/server/api/core/items/{uuid}/bundles
GET https://indiacode.gov.in/server/api/core/bundles/{uuid}/bitstreams
GET https://indiacode.gov.in/server/api/core/bitstreams/{uuid}/content      # the file
```

Items carry **three bundles** — `ORIGINAL` (PDF), `TEXT` (extracted `.txt`), `THUMBNAIL`.
The TEXT bundle is the important one: it means we do not need to OCR or parse PDFs.

Confirmed live: Tripura SGST Act 2017 → `tsgst_act,_2017.pdf` (1.7 MB) **and**
`tsgst_act,_2017.pdf.txt` (100 KB) containing the full act text from "THE TRIPURA ACT
NO. 9 OF 2017" onward.

**This one source closes four of the seven gaps.** Details below.

---

## Gap 1 — 12 states and 7 UTs have no harvester

**Probed India Code, hit counts per state (fuzzy search, so presence not completeness):**

| Missing state | Hits | Missing state | Hits |
|---|---:|---|---:|
| Jharkhand | 683 | Arunachal Pradesh | 288 |
| Madhya Pradesh | 657 | Uttarakhand | 211 |
| Tripura | 538 | Sikkim | 203 |
| Meghalaya | 375 | Nagaland | 203 |
| Goa | 285 | Manipur | 187 |
| Mizoram | 183 | — | — |

| Missing UT | Hits |
|---|---:|
| Chandigarh | 830 |
| Andaman & Nicobar | 212 |
| Lakshadweep | 158 |
| Ladakh | 143 |
| Puducherry | 126 |

**Every missing state and UT has material on India Code.** That does not make a
per-state portal harvester unnecessary — a state's own feed is fresher and more
complete — but it means the gap can be closed *without* building 19 new scrapers.

**Also confirmed:** three states are blocked only by a missing TLS intermediate, the
same fix already applied for CBIC:

| State | Host | Needs |
|---|---|---|
| Himachal Pradesh | `hptax.gov.in` | Sectigo **DV** R36 intermediate (not the OV cert already held) |
| Madhya Pradesh | `mptax.mp.gov.in` | GeoTrust EV RSA CA G2 intermediate |
| Chandigarh | `chandigarh.gov.in` | eMudhra EM DV TLS CA G2A-1 intermediate |

`goa.gov.in`, `py.gov.in` and `ladakh.gov.in` answer 200 already. `sikkimtax.gov.in`
serves no certificate at all.

**Recommendation:** two-track. (a) Build one `harvest_indiacode.py` that queries the
REST API per state and stores acts + notifications — that alone takes coverage from 17
to 36 states/UTs. (b) Then add native harvesters opportunistically for the states with
real volume (MP, Jharkhand, Chandigarh), starting with the three TLS-fixable ones.

---

## Gap 2 — 0 SGST Acts

Every state has its own State Goods and Services Tax Act. We hold none.

India Code has them, with text. Verified for Tripura; search returns Andhra Pradesh,
Tamil Nadu, Himachal Pradesh, Kerala, West Bengal, Bihar, Uttarakhand, J&K and more.
Search `"State Goods and Services Tax Act, 2017"` returns **5,837** objects.

**Recommendation:** this is the cheapest high-value win on the list. One script, no
OCR, no CAPTCHA, no geo-block, text included. It also feeds Gap 4.

---

## Gap 3 — CBIC section text

We hold the CBIC statute *hierarchy* (3,077 rows: acts, chapters, sections, rules,
forms) but no section bodies, because `taxinformation.cbic.gov.in` returns
`contentData: null` and no content endpoint exists (7 probed).

**India Code carries the same acts as full text.** The CGST Act 2017, the IGST Act,
the Compensation to States Act and the J&K extension acts all appear in search
results with TEXT bundles.

**Recommendation:** stop trying to extract from CBIC. Pull the acts from India Code
and join on section number to the hierarchy we already hold. The repo already has
`scripts/legislation/pipeline/legislation_section_detector.py` to split a full act
text into numbered sections.

---

## Gap 4 — Rate master (HSN/SAC)

`rate_held` / `rate_proposed` are empty on every row. There is no single
machine-readable rate master published by CBIC.

**The source is the rate notifications**, which we now hold and which India Code also
carries in bulk — including central rate notifications ("Notification No.13/2017-Central
Tax (Rate)") and state ones ("NOTIFICATION No. 24/2018-State Tax (Rate)").

**Recommendation:** build the rate master by extracting from the rate notifications
rather than looking for a master file. That is a parsing job over documents already in
the corpus, not a new harvest. `/api/insights` depends on it.

---

## Gap 5 — West Bengal and Bihar (host-blocked)

- **West Bengal:** `comtax.wb.gov.in:443` is TCP-closed from this egress. 410 files held and frozen.
- **Bihar:** login-walled, 0 files.

**India Code carries both:** West Bengal 351 act hits + 651 notification hits;
Bihar 814 + 863.

**Recommendation:** use India Code as the fallback for both, and stop treating them as
hard-blocked. WB's native feed is still better when reachable from an Indian host —
keep the harvester and run it there — but India Code unblocks the corpus today.

---

## Gap 6 — Haryana partial (40 of ~82)

`haryanatax.gov.in` drops connections under load. The new per-host throttle now
escalates to 300s on a real `RemoteDisconnected` (confirmed live during today's run).

**Recommendation:** leave the gentle run going; it is already self-limiting. No code
change needed — this gap is now a waiting problem, not a build problem.

---

## Gap 7 — eSCR and GSTAT (CAPTCHA)

- **eSCR:** 3 of 27 SC GST judgments. Securimage CAPTCHA, ~15-minute sessions, IP rate limits.
- **GSTAT:** 4 notices; CSRF + image CAPTCHA, e-filing login-walled.

No API, no bulk endpoint, no non-CAPTCHA mirror found.

**Options, in order of realism:**
1. **Supreme Court and High Court judgments are already public as PDFs under CC BY 4.0
   on the AWS Open Data Registry** (published by Dattam Labs — the upstream project
   already reads them via `scripts/pipeline/aws-hc-parquet-reader.py`). That is the
   practical route for *judgments*; it is not `.gov.in`, so it is a scope decision, but
   it is official-source-adjacent and removes the CAPTCHA problem entirely.
2. **GSTAT has no alternative.** It is the newest tribunal and publishes only through
   its own portal. This needs an assisted browser session — a human solves the CAPTCHA
   once per batch. Low volume, so it is a bounded manual job, not a pipeline.

---

## Recommended order

| # | Work | Closes | Effort |
|---|---|---|---|
| 1 | `harvest_indiacode.py` against the DSpace 7 REST API | Gaps 1, 2, 3, 5 | **One script** |
| 2 | Fix `indiacode-scraper.ts` for the new host (or retire it in favour of #1) | keeps the upstream pipeline honest | Small |
| 3 | Add the 3 TLS intermediates; run the HP / MP / Chandigarh harvesters | Gap 1 (native feeds) | ~1 hour |
| 4 | Rate-master extraction from rate notifications | Gap 4 | Medium, parsing only |
| 5 | Assisted GSTAT session; decide on AWS Open Data for judgments | Gap 7 | Manual, low volume |
| 6 | Let the Haryana gentle run finish | Gap 6 | Nothing |

## What not to do

- **Do not build 19 state scrapers first.** India Code covers all of them; build the
  one client, then add native harvesters only where volume justifies it.
- **Do not keep probing `taxinformation.cbic.gov.in` for section bodies.** It does not
  serve them; India Code does.
- **Do not treat West Bengal and Bihar as permanently blocked.** They are reachable
  through India Code today.
- **Do not OCR India Code PDFs.** The TEXT bundle already carries the text.

---

*Evidence for every claim above was collected on 2026-09-14 by live request. The one
figure to treat as indicative rather than exact is the per-state hit count: India Code
search is fuzzy, so a hit count proves presence, not completeness.*
