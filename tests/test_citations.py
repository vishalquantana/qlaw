"""Pins for the three citation types added in Phase 0.

All three patterns are written against real phrasings taken from the corpus. The
sample strings below are the actual forms found, not invented ones — circular
formats in particular vary (`51/25/2018-GST`, `3/1/2018`, bare `164`).
"""
from __future__ import annotations

from gst_aar_law_shim import extract_ontology as eo


class TestCircularPattern:
    def test_three_part_number_with_suffix(self) -> None:
        m = eo.CIRCULAR_RE.search("as clarified by Circular No. 51/25/2018-GST dated 31/07/2018")
        assert m is not None
        assert m.group(1).replace(" ", "") == "51/25/2018-GST"

    def test_three_part_number_without_suffix(self) -> None:
        m = eo.CIRCULAR_RE.search("Circular No. 3/1/2018 dated")
        assert m is not None

    def test_no_space_after_No(self) -> None:
        assert eo.CIRCULAR_RE.search("Circular No.28/02/2018-GST") is not None

    def test_two_part_number(self) -> None:
        assert eo.CIRCULAR_RE.search("circular No. 33/2017-") is not None

    def test_does_not_match_a_generic_mention(self) -> None:
        # real text: "circulars dated 19.05.2023 issued by the Regional Port Officer"
        assert eo.CIRCULAR_RE.search("circulars dated 19.05.2023 issued by the") is None

    def test_does_not_match_the_bare_word(self) -> None:
        assert eo.CIRCULAR_RE.search("circulars and notifications") is None


class TestSchedulePattern:
    def test_entry_of_schedule(self) -> None:
        m = eo.SCHEDULE_RE.search("Entry 234 of Schedule III")
        assert m is not None
        assert m.group(1) == "234" and m.group(2).upper() == "III"

    def test_sr_no_form(self) -> None:
        m = eo.SCHEDULE_RE.search("Sr. No. 45 of Schedule II")
        assert m is not None
        assert m.group(1) == "45"

    def test_bare_schedule_reference(self) -> None:
        m = eo.SCHEDULE_RE.search("goods specified in Schedule II")
        assert m is not None
        assert (m.group(3) or "").upper() == "II"

    def test_roman_numeral_only(self) -> None:
        # must not fire on an arabic numeral, which is a section or rule number
        assert eo.SCHEDULE_RE.search("Schedule 2") is None


class TestPrecedentPattern:
    def test_tmi_citation(self) -> None:
        m = eo.PRECEDENT_RE.search("reported at 2022 (9) TMI 418")
        assert m is not None
        assert m.group(1) == "2022" and m.group(3).upper() == "TMI" and m.group(4) == "418"

    def test_elt_citation(self) -> None:
        m = eo.PRECEDENT_RE.search("2010 (258) ELT 321")
        assert m is not None
        assert m.group(3).upper() == "ELT"

    def test_scc_and_gstl(self) -> None:
        assert eo.PRECEDENT_RE.search("2004 (6) SCC 123") is not None
        assert eo.PRECEDENT_RE.search("2022(62) GSTL 45") is not None

    def test_does_not_match_a_bare_year_in_brackets(self) -> None:
        assert eo.PRECEDENT_RE.search("(2019) 12 something else") is None

    def test_does_not_match_a_section_number(self) -> None:
        assert eo.PRECEDENT_RE.search("section 22 (3) of the Act") is None


class TestRateSlabs:
    """The slab set is read from the rate schedule rather than hardcoded, because a
    hand-written list missed 3.75% and 7.5% — real rates for construction services."""

    def test_slabs_load_from_the_schedule(self) -> None:
        slabs = eo.load_valid_slabs()
        assert slabs, "rate_facts should yield a slab set"
        for expected in (0.0, 2.5, 6.0, 9.0, 14.0, 18.0, 28.0):
            assert expected in slabs, expected

    def test_construction_rates_are_present(self) -> None:
        # the values a hardcoded list got wrong
        slabs = eo.load_valid_slabs()
        assert 3.75 in slabs
        assert 7.5 in slabs

    def test_nil_maps_to_zero(self) -> None:
        assert 0.0 in eo.load_valid_slabs()


class TestRateExtraction:
    def _slabs(self):
        return {0.0, 1.5, 2.5, 3.75, 5.0, 6.0, 9.0, 12.0, 14.0, 18.0, 28.0}

    def test_word_then_number(self) -> None:
        assert eo.extract_rates("the rate of tax applicable is 18% on such supply",
                                self._slabs()) == ["18"]

    def test_number_then_word(self) -> None:
        assert eo.extract_rates("taxable @ 2.5% CGST and 2.5% SGST",
                                self._slabs()) == ["2.5"]

    def test_a_percentage_with_no_rate_context_is_ignored(self) -> None:
        # real text: "the applicant has 25 employees and 40% turnover"
        assert eo.extract_rates("the applicant has 25 employees and 40% turnover",
                                self._slabs()) == []

    def test_a_rate_context_with_a_non_slab_value_is_ignored(self) -> None:
        # 15% is not a GST rate, even though it sits next to "rate"
        assert eo.extract_rates("the rate of interest is 15% per annum",
                                self._slabs()) == []

    def test_most_frequent_rate_comes_first(self) -> None:
        text = "rate of 18% applies. the rate of 12% applies. rate of 18% again"
        assert eo.extract_rates(text, self._slabs())[0] == "18"

    def test_no_slabs_means_no_extraction(self) -> None:
        assert eo.extract_rates("the rate is 18%", set()) == []

    def test_empty_text(self) -> None:
        assert eo.extract_rates("", self._slabs()) == []


class TestFocusExcerpt:
    """The excerpt is centred on the operative part of a ruling.

    Taking the first 9,000 characters sent mostly recital: 74% of decisions sit beyond
    that point and the median decision is halfway through the document. The first
    measurement of this fix sampled the largest rulings and tested a window that still
    stopped short of the decision, producing a confident wrong answer.
    """

    def _doc(self, decision_at: int, total: int = 80000) -> str:
        pad = "x" * decision_at
        rest = "y" * max(0, total - decision_at - 40)
        return pad + " In view of the above, we rule as under: " + rest

    def test_the_decision_is_included(self) -> None:
        ex = eo.focus_excerpt(self._doc(40000))
        assert "we rule as under" in ex

    def test_the_excerpt_is_much_smaller_than_the_document(self) -> None:
        doc = self._doc(40000)
        assert len(eo.focus_excerpt(doc)) < len(doc) // 3

    def test_a_decision_near_the_end_is_still_reached(self) -> None:
        # the case the first experiment failed on
        ex = eo.focus_excerpt(self._doc(70000))
        assert "we rule as under" in ex

    def test_a_decision_near_the_start_is_still_reached(self) -> None:
        ex = eo.focus_excerpt(self._doc(200))
        assert "we rule as under" in ex

    def test_no_marker_falls_back_to_the_head(self) -> None:
        ex = eo.focus_excerpt("z" * 50000)
        assert len(ex) == 20000
        assert ex == "z" * 20000

    def test_empty_text_falls_back_to_the_brief(self) -> None:
        assert eo.focus_excerpt("", "the brief") == "the brief"

    def test_every_decision_marker_anchors_the_window(self) -> None:
        for phrase in ("we hold that", "held that", "we are of the opinion",
                       "the question is answered", "the application is hereby rejected"):
            doc = "a" * 30000 + f" {phrase} something " + "b" * 30000
            assert phrase in eo.focus_excerpt(doc), phrase
