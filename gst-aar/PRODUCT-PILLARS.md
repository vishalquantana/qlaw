# GST corpus — product pillars

**Date:** 17 September 2026 · **Status:** planning document, for the department's review

Three use cases the department has asked for. This document sets out what the tool
does **today**, what each use case actually requires, and the order in which the
work should be done. It is deliberately blunt about the gap — the second half of
this document is mostly a list of things that do not exist yet.

---

## 1. Baseline — what the tool does today

**It finds and explains. It does not judge, aggregate or generate guidance.**

| Capability | Route | State |
|---|---|---|
| Keyword search over rulings | `/api/search` | works — FTS5, state and date filters |
| Semantic search over rulings | `/api/semantic` | works — vector similarity |
| Hybrid Q&A over rulings | `/api/ask` | works — vector + BM25 fused, then LLM answer |
| Retrieval Q&A across corpus | `/api/chat` | works — retrieves from both `aar.db` and `law.db` |
| Keyword search over legislation | `/api/law` | works |
| Rate lookup by HSN / SAC | `/api/rate`, CLI | works — 1,085 codes |
| Document view / PDF | `/api/document`, `/api/pdf` | works |

**Corpus behind it:** 13,126 documents — 702 of 769 central Act sections worded,
all 163 CGST Rules, 1,821 rate lines over 1,085 codes, 2,888 advance rulings,
6,350 state notifications, 59 Council papers.

So the tool answers *"what does the law say"* and *"what has been held about X"*.
It cannot answer *"is this order correct"*, *"why do these disputes keep happening"*
or *"what should an industry watch out for"*. Those are the three pillars.

---

## 2. The foundation gap — and it is the headline finding

All three use cases rest on one atomic unit, which I will call a **decision record**:

> an issue that was disputed → the provision that governs it → how it was decided →
> the reasoning, with citations

**That unit exists for 729 of 2,888 rulings — 25%.** On the stricter reading, where the
governing provision must be a *section* (471 of 2,888 — 16%), it is thinner. Both
figures are reported by `pillar_baseline.py`; the definition matters, so it is stated
rather than implied. It stood at **216 (7%)** before Phase 0 — the work in §2a has
more than tripled it.

**Which side is the bottleneck?** A record needs both a citation and an outcome, so the
scarcer input is what limits it — and that is now unambiguously **outcomes**:

| | Rulings | Of 2,888 |
|---|---:|---:|
| Have any provision citation | 2,679 | **93%** |
| Have a section citation | 1,796 | 62% |
| Have a rate recorded | 1,281 | **44%** |
| Have an issue outcome | 823 | **28%** |

The citation and rate sides are largely solved; the outcome side is the constraint.
That is why the in-flight questions pass matters, and why it is the right thing running.

The full picture from `aar.db`:

| Field | Populated | Of | Coverage |
|---|---:|---:|---:|
| Ruling has a recorded outcome | 1,950 | 2,888 | 68% |
| Question has an outcome | 1,323 | 5,383 | **25%** |
| Question has a held-summary | 929 | 5,383 | **17%** |
| Subject carries a rate | 1,973 | 4,545 | **43%** |
| Citations — kinds present | 6 | 6 | **complete** |

All three problems this section previously listed are now **fixed**:

- ~~**No controlled vocabulary.**~~ `normalize_vocab.py` collapses
  `ruling_subjects.kind` to `good` / `service` / `both` / `unspecified`, both outcome
  columns share one vocabulary, and rate values are canonicalised so `18` and `18%`
  aggregate as one.
- ~~**Missing citation types.**~~ All six extracted; citation rows 4,463 → 12,184.
- ~~**Rate linkage absent.**~~ **44% of rulings now carry a rate**, up from 2%.

**A decision record view now exists** (`decision_record` in `aar.db`), joining issue →
provision → outcome → held-summary → sector, so the three pillars have one place to
query instead of three unjoined tables.

**The questions pass currently running will improve the outcome and held-summary
figures.** It covers 878 more rulings (~4.5 hours from writing). Even when it
finishes, the decision record is the binding constraint on all three pillars.

---

## 2a. Phase 0 — progress

| Item | State |
|---|---|
| Controlled vocabularies | **done** — subject kind (7 → 4 concepts), one shared outcome vocabulary, rates canonicalised |
| Decision record | **done** — `decision_record` view, carrying all six citation types and rates |
| Citation completion | **done** — `circular` (405), `schedule_entry` (1,094), `precedent` (468); 6/6 kinds |
| Rate linkage | **done** — 2% → **44%** of rulings carry a rate |
| Evaluation harness | **built** — automated checks running; expert labels still needed before any accuracy claim |

**Combined effect:** the decision record went from **216 → 729 rulings (7% → 25%)**.

### The evaluation harness

`eval_harness.py` does three things: runs automated integrity checks, draws a
stratified sample for expert labelling, and scores the returned labels. It is explicit
about its own limits — it measures whether what we extracted is *internally consistent
and resolvable*, which is not the same as *legally correct*. Only an expert can settle
the latter, which is what the label sheet is for.

Current results:

| Check | Result |
|---|---:|
| Central-Act section citations resolving | **1,427 / 1,430 — 100%** |
| HSN / SAC codes found in the rate schedule | 1,686 / 1,792 — 94% |
| Recorded rates on a real GST slab | 1,891 / 1,895 — **100%** |
| Rulings with conflicting rates between passes | 137 of 1,281 — 11% |

The first version of the resolvability check reported **67%** and was wrong: it keyed
on the section number alone, and **161 of 174 section numbers are shared between Acts**,
so "s.98" matched the Customs Act's section 98 as readily as the CGST Act's. Keyed
correctly on (Act, number) it is 100%. A check that produces a plausible-but-wrong
number is worse than no check.

### Finding: State GST Act sections are not held, and do not split easily

The harness surfaced that **2,385 of the 3,815 section citations — the majority — are
to State GST Acts** (`SGST s.98(4)` alone appears 350 times). We hold each State Act as
a single 100–600 KB document, so none of those citations resolves to a section.

`split_sgst_acts.py` was written to fix that, and the honest result is that **it works
for one Act out of 74**. The state Acts are not one gazette format:

| Layout | Acts | Splits today? |
|---|---:|---|
| Marginal note (heading set in the margin, after the text) | 37 | no — needs column-aware extraction |
| Unrecognised | 31 | no |
| Arrangement of Sections index | 5 | index usable as a skeleton |
| Inline heading (Goa) | 1 | **yes** — 169 of 174 sections |

The tool **refuses to write a parse it does not believe** rather than storing a handful
of stray "sections" that would look like coverage. Splitting the remaining Acts is
scoped per-format work, not a one-pattern job — and the "Arrangement of Sections" index
in five of them is the most promising route, since it gives the section list directly.

Three notes from doing the work, all worth keeping:

- **Validate extraction patterns against a corpus-wide scan, not a handful of
  documents.** The first circular pattern returned zero because it was probed on the
  12 largest rulings, which happened to contain no numbered circulars. Scanning all
  2,888 found 323 rulings citing them — a working pattern nearly discarded over a
  sampling artefact.
- **Derive controlled sets from the data, not from memory.** The valid-rate set is read
  from our own rate schedule. A hand-written slab list missed **3.75% and 7.5%** — real
  rates for construction services. Reading it means it cannot drift.
- **A bare percentage is not a rate.** Rates are only extracted when a number sits next
  to a rate word *and* is a real slab. "the applicant has 25 employees and 40% turnover"
  yields nothing, correctly.

Two deliberate limitations:

- **Precedent extraction is narrow** — reporter-style citations only
  (`2022 (9) TMI 418`). Party-name precedent ("X v. Commissioner") is too free-form for
  a regex and would generate noise; it is left to the LLM pass.
- **`rate_proposed` is the rate under discussion, not the rate determined.** Separating
  the two needs the LLM pass; `rate_held` remains sparse at 2% and is not used as a
  decision field.

---

## 3. Pillar 1 — review whether an order is according to law

**The hardest of the three, and the one with the highest bar.**

### What it actually requires

Not one capability but a pipeline of five:

1. **Order ingestion.** Accept a PDF or text order and extract structure: parties,
   period, the demand, the findings, the reasoning, the operative decision.
2. **Position extraction.** State, explicitly, what the order asserts — as fact and
   as law. This is where most naive attempts fail: an order's *stated* basis and its
   *actual* basis often differ.
3. **Provision retrieval.** For each issue raised, find the governing sections,
   rules and notifications.
4. **Compliance test.** Compare the order's position against the provision. The
   checkable departure types:
   - **wrong provision** cited, or a repealed one
   - **provision misread** — a limb omitted, a proviso or explanation ignored
   - **rate or classification error** — checkable mechanically against `rate_facts`
   - **limitation / time-bar** error
   - **natural justice** — no show-cause notice, no personal hearing offered
   - **precedent ignored** — a ruling on the same point not considered
5. **Output.** A structured finding per issue: issue, the order's position, the
   governing provision, the assessment, the citation, and a confidence.

### What we have and what is missing

| Need | Have | Missing |
|---|---|---|
| Provisions | 702 sections, 163 rules | — |
| Rates | 1,085 codes | — |
| Precedent | 2,888 rulings, searchable | decision records (7%) |
| Order structure model | — | **all of it** |
| Compliance checklist | — | **the rule set** |
| Requirement model per provision | — | **"what must be satisfied"** |

### The framing constraint — read this before scoping

**This must be built as a review aid, not an adjudicator.** A tool that tells an
officer "this order is unlawful" is a liability: it will be wrong sometimes, and
when it is wrong the cost lands on the department. The correct output is:

> "The order relies on section X. Section X contains a proviso at sub-section (3)
> which the order does not address. **Verify.**" — with the provision quoted.

Every finding must carry the provision verbatim and be framed as *flag for human
review*. Nothing should be asserted as a conclusion of law. This is also what makes
the pillar defensible: the tool never substitutes for the officer's judgment, it
makes sure the officer sees the provision that matters.

### Hardest sub-problem

The **requirement model** — for each provision, what a valid order must satisfy.
Sections state obligations in prose. Turning 702 sections into checkable
requirements is a large, expert-dependent task, and it is the long pole. A defensible
first cut: cover only the provisions that actually generate disputes, which the
citation data can identify — the top cited are SGST s.98(4) (123), s.97 (105),
s.7 (63), s.98(2) (51), CGST s.2 (39), SGST s.16 (37).

---

## 4. Pillar 2 — root causes of common disputes

**Medium difficulty. Mostly aggregation, but it depends entirely on the taxonomy.**

### What it requires

1. **A cause taxonomy — the missing piece.** Nothing in the corpus classifies *why*
   a dispute arose. Candidate axes, to be validated with the department:

   | Axis | Causes |
   |---|---|
   | Drafting | ambiguity, undefined term, proviso conflicting with the main limb, retrospective effect, drafting error |
   | Interpretation | limb omitted, explanation ignored, two readings genuinely open |
   | Classification | HSN/SAC ambiguity, composite supply, principal vs ancillary |
   | Valuation | transaction value vs rules 27–35, related-party |
   | Input tax credit | eligibility, blocked credit s.17(5), time limit, documentary |
   | Rate | notification rate vs tariff rate, exemption vs concessional |
   | Procedure | notice, limitation, jurisdiction, natural justice |
   | Transition | carry-forward of credit |

2. **Attribution.** Classify each dispute to one or more causes, at scale, with a
   human-validated sample to measure agreement.
3. **Aggregation.** Cause × sector × provision → which causes dominate, and which
   provisions generate the most disputes.
4. **Recommendation.** For each dominant cause, what would reduce it — a drafting
   fix, a clarification circular, a guidance note.

### What is missing

The taxonomy, the attribution, and the aggregation. And the outcome data — with 20%
of questions carrying an outcome, we cannot yet distinguish *"disputed and clarified
in the assessee's favour"* from *"disputed and rejected"*. **The department's steer
on what counts as a root cause matters more here than any engineering.** "Bad
drafting" is a conclusion the tool should support with evidence, not assert.

### The honest constraint

Root-cause attribution is an *interpretive* claim. A tool that says "38% of
classification disputes stem from drafting ambiguity" is making an analytical
judgment. It must show its work — the specific rulings behind each bucket, so an
officer can disagree with a click.

---

## 5. Pillar 3 — industry guides from rulings and cases

**Easiest of the three. Synthesis of material we already hold, low risk.**

### What it requires

1. **Industry mapping.** From sector tags to a guide structure. We have 17 tags
   (manufacturing 1,026 rulings, construction 621, energy 426, transport 425,
   agriculture 306, education 286, finance 265, healthcare 254, hospitality 200,
   retail 157, it-services 142, professional-services 83, media 66) — useful but
   **too coarse and single-level** for a guide.
2. **Issue clustering per industry** — group the rulings within an industry by issue.
3. **Product-level caveats** — map HSN/SAC codes and descriptions to caveats, which
   is where the rate reference and the ruling subjects meet.
4. **Generation** — a structured guide per industry: common issues, what the rulings
   held, caveats for products, watch-outs, citation to authority.
5. **Regenerability** — guides must be rebuildable as rulings and notifications
   change, or they go stale silently.

### Why this is first

It is **synthesis, not judgment.** It organises what the rulings already say and
attributes every statement to a citation. It makes no new claim about the law, so
the accuracy bar is lower and the failure mode is mild (a poorly grouped section,
not a wrong legal conclusion).

---

## 6. Cross-cutting requirements

These serve all three pillars and should be treated as one workstream:

1. ~~**Controlled vocabularies** for subject kind, dispute cause, industry, provision
   type and outcome.~~ **Done for subject kind, outcome and rate**; still needed for
   **dispute cause** and **industry** (both are new taxonomies, §4 and §5).
2. ~~**The decision record**~~ — **the view exists and carries all six citation types
   and rates**; it still needs *outcome* density, which is the item below.
3. ~~**Citation completeness**~~ — **done**, all six kinds extracted.
4. ~~**Rate linkage**~~ — **done**, 2% → 44%.
5. **Outcome completeness** — still the binding constraint (~28% of rulings), and now
   diagnosed: **95% of the missing outcomes are present in the text and not being
   extracted** (§2b). The fix is the extraction, not the corpus. **Inferring an outcome
   is still not acceptable** — a blank outcome is honest, a guessed one is not.
6. **State GST Act sections** — the majority of section citations in the rulings point
   at State Acts we hold only as whole documents. Splitting them is per-format work
   (§2a).
7. **Expert labels** — the harness is built, but an accuracy figure needs the
   department to fill in the label sheet. Without it none of these three pillars
   should be put in front of an assessing officer.

## 2b. The outcome gap — two wrong answers, and what the text actually says

This is worth setting out in full because the reasoning went wrong twice, in
instructive ways.

The extraction prompt sends only the first 9,000 characters of a ruling, and **78% of
rulings are longer** (median 18,458, p90 47,407, longest 166,216). Separately, **92% of
the question rows with no outcome come from a truncated ruling** (4,061 of 4,417).

**First answer — "truncation is not the cause."** A sample re-run with a four-times
wider window recovered an outcome for only 4 of 25 rulings, so I concluded the gap was
largely genuine. **That experiment was confounded.** It sampled `ORDER BY chars DESC` —
the *largest* rulings, 96,000–166,000 characters — and tested a 40,000-character window.
Forty thousand characters covers only the first quarter of those documents, so the
decision was still outside the window being tested. It measured nothing about truncation.

**Second answer — ask the text directly, no LLM involved.** `diagnose_outcomes.py` reads
the full orders and looks for the sentences a ruling uses when it actually decides:

| of 300 rulings with an unknown outcome | |
|---|---:|
| order genuinely silent | 14 (5%) |
| withdrawal / disposal only | 1 |
| **a decision sentence exists in the text** | **284 (95%)** |

Markers found: *"in view of the above"* 219, *"we rule"* 155, *"held that"* 152,
*"we are of the opinion"* 72, *"we hold"* 58. Ruling 22 reads, in the order's own words:

> *"In view of the above, we rule as under: - RULING Q.1. Whether the supply of Paper
> Bags' made out of paper or paper board, classifiable under Heading 4819…"*

**So the outcome is in the text and we are not getting it. The gap is an extraction
failure, not a genuine absence.** That reverses the first answer.

**Where the decision sits**, which is why the cap matters:

| position in the document | |
|---|---:|
| after character 9,000 (the production cap) | **74%** |
| median | 49% |
| p75 | 89% |
| p90 | 94% |

Three-quarters of decisions are beyond the cap, and the median decision sits halfway
through a document that the prompt half-reads.

**Third answer — run it properly.** A corrected experiment sends the **full text**, and
samples on *where the decision sits* rather than on document size:

| | experiment 1 (40k window, sampled by size) | experiment 2 (full text, sampled by position) |
|---|---:|---:|
| Rulings gaining an outcome | 4 of 25 — **16%** | 16 of 20 — **80%** |

Same question, same corpus, opposite answers. **Truncation is the cause**, and the
first experiment was simply incapable of showing it.

| | today | projected |
|---|---:|---:|
| Rulings with a recorded outcome | 823 of 2,888 (28%) | **~2,441 (85%)** |

**The fix being applied** is not full text — that measured ~56s per ruling, roughly 31
hours for the backlog. Instead the excerpt is **centred on the decision sentence**
(`focus_excerpt`, a 16,000-character window around the first decision marker), which
reaches the same material for a fraction of the tokens. The pass is also made
idempotent so a re-run replaces rather than duplicates rows.

**The lesson, and it is the more valuable one: sample on the property you are testing,
not on a convenient proxy.** Ordering by document size selected precisely the cases
where the intervention could not work, and produced a confident wrong answer that I
then repeated into three generated guides. A correlation on 4,000 rows is not a cause —
and neither is an experiment that never reached the thing it was testing.



---

## 7. Sequencing

| Phase | Work | Why this order |
|---|---|---|
| **0** | Controlled vocabularies, decision record, citation completion, eval harness | Everything else is built on this; doing it later means rebuilding |
| **1** | **Industry guides** (Pillar 3) | Synthesis only, no legal claims, lowest risk — proves the decision record works |
| **2** | **Dispute root causes** (Pillar 2) | Aggregation over the decision record; needs the taxonomy validated by the department |
| **3** | **Order review** (Pillar 1) | Highest accuracy bar, needs the requirement model and the eval harness to be credible |

**The tempting mistake is to start with Pillar 1** — it is the most impressive demo.
It is also the one that will produce a confidently wrong answer in front of an
assessing officer, and that failure would cost the whole project its credibility.
Phase 0 is not optional.

---

## 8. What we must not claim

- **Not legal advice.** The tool surfaces provisions and holdings; it does not decide.
- **Order review flags for human review.** It never concludes that an order is
  unlawful, only that a provision or proviso appears unaddressed.
- **Guides are drafts** and require departmental review before issue.
- **Accuracy must be measured, not asserted.** Until the eval harness reports a
  figure, no accuracy claim should be made to anyone.
- **Blank is better than guessed.** Where the corpus does not record an outcome, it
  stays blank.

---

## 9. Open questions for the department

1. **What counts as a root cause?** Our candidate taxonomy (§4) needs validating —
   particularly whether "bad drafting" should be a category the tool assigns, or
   something an officer concludes from evidence the tool presents.
2. **What is the expected output of an order review?** A checklist against the
   order? A draft para? A risk flag? The answer changes the design substantially.
3. **Which industries matter most** for the first guides? We would start with the
   three largest by ruling volume — manufacturing, construction, energy.
4. **Who reviews generated guides** before they are issued, and in what form?
5. **Is there an internal corpus of past orders** we could use to build and test the
   order-review pillar? Public rulings alone may not represent the department's own
   order patterns, and a golden set of real orders would be the single biggest
   accelerant for Pillar 1.
