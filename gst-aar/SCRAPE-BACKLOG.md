# What else could be scraped — an evidence-based backlog

**Date:** 20 September 2026 · Companion to `PRODUCT-PILLARS.md`

Everything below is measured against the corpus as it stands, not estimated. Each item
says what is missing, what it would take, and — where relevant — **what should not be
scraped**, which matters as much as what should.

---

## 1a. The rate notifications — and a much smaller fix than the archive

Working the client's mock order (`orders/sample-buildcon-appeal.txt`) showed that the
gaps are not evenly weighted. The order turns on whether **Notification 03/2019-CTR**
(inserting para 2A into Notification 11/2017-CTR) may be applied to a supply whose
point of taxation the Adjudicating Authority fixed at 10-03-2019, when the amendment is
asserted to be effective 01-04-2019.

The corpus does **not** hold the instruments — but it does contain rulings that quote
them and cite the authorities, which is usable secondary evidence:

| Evidence in the corpus | Rulings |
|---|---:|
| para 2 text quoted | 18 |
| para 2A text quoted | 1 |
| the prospectivity principle, as stated and attributed | 1 |
| the clarificatory / prospective distinction | 6 |
| **the effective date of 03/2019-CTR** | **0** |

**So the gap is one document, not an archive.** The reasoning can be supported from
secondary evidence; the *effective date* — the single fact the whole analysis rests on
— cannot. That is **Notification 03/2019-CTR itself**.

This matters for sequencing: pulling 47 circulars is worthwhile but not urgent; pulling
**one notification** would let the tool move from *"the reasoning looks internally
inconsistent"* to a supported position. Worth doing first.

A note on why the distinction between holding a document and quoting it is real, not
pedantic: the department's answer to this order would be that the amendment is
**clarificatory**, and therefore retrospective — which defeats the reasoning entirely.
Whether it is clarificatory turns on the instrument's own words. A quotation in a
ruling cannot settle that; the instrument can.

---

## 1b. The 47 circulars the rulings cite and we do not hold

**This is the most valuable gap, and it sits inside the officer's own top layer.**

Circulars are how CBIC clarifies the law between amendments, and the rulings lean on
them heavily. Comparing what the rulings cite against what we hold:

| | count |
|---|---:|
| Distinct circulars cited by rulings | 137 |
| Distinct circulars held in the corpus | 209 |
| **Overlap** | **65** |
| **Cited but not held** | **47** |

The missing ones are not a random tail. The three most-cited circulars in the whole
corpus are all missing:

| Circular | Cited |
|---|---:|
| `52/26/2018-GST` | **41 times** |
| `51/25/2018-GST` | **21 times** |
| `80/54/2018-GST` | **18 times** |

And the gap clusters exactly where you would expect — the early GST years, when the
scheme was being explained: **2017: 9 missing · 2018: 11 · 2019: 6** — 26 of the 47.

**Why it matters beyond completeness:** a ruling that says *"as clarified by Circular
52/26/2018-GST"* is currently a dead end for the reader. The citation is extracted and
searchable, but the document behind it is not in the corpus, so the tool cannot show
what the clarification actually said.

**What it would take:** the CBIC circular archive. Note this is a **repair job, not new
scraping** — see §5.

---

## 2. About 2,300 rows in the "Central Acts, Rules and sections" layer are metadata stubs

The report counts this layer at 3,164 documents. Measured by substance, most of it is
not there:

| Kind | Rows | With substantial text | Avg body |
|---|---:|---:|---:|
| `cbic_rule_section` | 1,294 | **2** | 71 chars |
| `cbic_form` | 428 | **0** | 48 chars |
| `cbic_regulation` | 217 | **0** | 51 chars |
| `cbic_rule_chapter` | 125 | **0** | 120 chars |
| `cbic_act_chapter` | 96 | **1** | 151 chars |
| `cbic_rule` | 96 | **0** | 123 chars |
| `cbic_amendment` | 37 | **0** | 103 chars |
| `cbic_act` | 15 | **0** | 73 chars |

A row in `cbic_rule_section` looks like this:

```
Rule: Rule 1 — Short Title and Commencement
Amended: 2021-09-18
```

That is a title and a date, not a rule. **The layer's real content is 702 Act sections
and the 163 CGST Rules** — the rest is a scaffold the CBIC API gave us and we never
filled.

**Two honest options**, and they should be a conscious choice rather than left as-is:

- **Fill them** — forms and regulations are short, and the CBIC publishes them; rule
  sections for the non-GST rule sets are a larger job with less GST relevance.
- **Stop counting them** — report the layer as "702 Act sections and 163 CGST Rules",
  which is true, rather than 3,164, which is not.

I would do both: fill forms and regulations, and correct the count either way.

---

## 3. Thin layers worth a look

| Layer | Held | Note |
|---|---:|---|
| Judgments | **3** | High Court GST judgments run to the thousands; this is essentially empty |
| GST Council minutes | 59 | The record of the Council's own reasoning on rate and procedural change |
| `gstat_notice` | 4 | The Appellate Tribunal — access is blocked, not overlooked |

**Judgments is the notable one.** It is the layer the officer's *order-review* pillar
would lean on hardest for precedent, and it is currently three documents.

---

## 4. What should NOT be scraped

**State GST notifications.** The department's steer was explicit: *"state notifications
are just a reproduction of Centre notifications. There's not much value addition
scraping those."* We hold 6,350 — the largest layer by count and the least valued.
**No further investment here.**

**State GST Act sections** are a **parsing** job, not a scraping one. We hold all 75
State Acts as whole documents; the work is splitting them, and it is blocked on the
gazette layouts differing between States (see `PRODUCT-PILLARS.md` §2a). Scraping more
copies would not help.

---

## 5. A repair job, not new scraping

**Both of the CBIC flat-listing sources the harvester uses now return 404:**

```
https://cbic-gst.gov.in/circulars.html                    -> 404
https://cbic-gst.gov.in/central-tax-notifications.html    -> 404
```

That is why we hold only recent circulars — they were found incidentally through
homepage links, not through the archive. The stream is broken and has been failing
quietly.

The newer `cbic.gov.in` serves a JavaScript application shell (a 3,372-byte page for
every path tried), and the `taxinformation.cbic.gov.in` API that gave us the CBIC
hierarchy **now returns HTML rather than JSON** at its former endpoints.

So this needs a source re-pointed, and it should be **checked periodically** — a
harvest stream that 404s silently is worse than one that fails loudly.

---

## 6. Suggested order

1. **Pull Notification 03/2019-CTR.** One document, and it unblocks the order-review
   pillar on a live example (§1a). Cheapest high-value item on this list.
2. **Re-point the CBIC stream and pull the 47 cited circulars.** They are the officer's
   layer, they are cited constantly, and three of them are the most-cited documents in
   the corpus.
3. **Correct the layer count in the report** (§2). It currently overstates the corpus,
   and the officer is reading those numbers.
4. **Fill `cbic_form` (428) and `cbic_regulation` (217).** Short documents, clear value.
5. **Judgments** (§3). Large and genuinely empty — but confirm with the department which
   forums matter before building a harvester.
6. **Council minutes.** Worth asking whether 59 is complete or whether a fuller source
   exists.

---

## A note on method

Two claims in this document were wrong on first pass and were caught by checking rather
than by reasoning:

- A first comparison suggested **zero** overlap between cited and held circulars. The
  naive match was broken; the true figure is 65 of 137.
- The `cbic_rule_section` rows *look* populated — the layer reports 100% "with text".
  They are stubs. **A count of non-empty bodies is not a count of content.**

Both are recorded because the same mistakes are available to anyone reading these
numbers later.
