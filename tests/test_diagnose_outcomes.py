"""Pins for the outcome-gap diagnostic.

The diagnostic exists to answer one question: is the missing outcome because the order
says nothing, or because we failed to extract what it said? Those need different fixes,
and (a) is not a defect at all. The marker patterns are what draw that line, so they are
what the tests cover.
"""
from __future__ import annotations

from gst_aar_law_shim import diagnose_outcomes as do


class TestDecisionMarkers:
    def test_the_markers_compile(self) -> None:
        assert do.COMPILED
        for rx, label in do.COMPILED:
            assert label

    def test_common_ruling_phrasings_are_caught(self) -> None:
        for text in (
            "In view of the above, we rule as under:",
            "we hold that the supply is exempt",
            "It has been held that the applicant is liable",
            "We are of the opinion that GST is payable",
            "The question is answered in the affirmative",
            "The application is hereby rejected",
        ):
            assert any(rx.search(text) for rx, _ in do.COMPILED), text

    def test_a_procedural_recital_is_not_a_decision(self) -> None:
        # a bare narrative sentence should not look like a ruling
        assert not any(rx.search("The applicant filed an application on 04-09-2023.")
                       for rx, _ in do.COMPILED)

    def test_matching_is_case_insensitive(self) -> None:
        assert any(rx.search("WE RULE as follows") for rx, _ in do.COMPILED)


class TestDisposalOnly:
    """A withdrawal or a rejection on maintainability is a disposition, not a decision
    on the substantive question — it belongs with 'order genuinely silent'."""

    def test_withdrawal_phrasings(self) -> None:
        for text in ("Application withdrawn as infructuous",
                     "the application is not maintainable",
                     "outside the purview of section 97",
                     "dismissed for non-prosecution",
                     "no manual copy was submitted"):
            assert do.DISPOSAL_ONLY.search(text), text

    def test_a_real_decision_is_not_flagged_as_disposal(self) -> None:
        assert not do.DISPOSAL_ONLY.search(
            "We hold that the supply of paper bags is classifiable under Heading 4819")
