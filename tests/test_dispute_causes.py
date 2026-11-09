"""Pins for the draft dispute-cause taxonomy.

The taxonomy is a draft for the department to validate, so two properties matter most:
every cause must be traceable to a signal a reader can check, and the signals must be
shown in the document as readable text. Both were got wrong on the first pass.
"""
from __future__ import annotations

from gst_aar_law_shim import dispute_causes as dc


class TestTaxonomyShape:
    def test_every_cause_has_a_gloss_and_signals(self) -> None:
        for cause, spec in dc.CAUSES.items():
            assert spec["gloss"], cause
            assert spec["text"], cause
            assert isinstance(spec["sections"], list), cause

    def test_the_glosses_are_readable_prose(self) -> None:
        # they are shown to a reviewer, so not bare keywords
        for cause, spec in dc.CAUSES.items():
            assert len(spec["gloss"]) > 20, cause

    def test_every_signal_compiles(self) -> None:
        assert set(dc.COMPILED) == set(dc.CAUSES)
        for cause, rxs in dc.COMPILED.items():
            assert rxs, cause

    def test_the_causes_the_plan_named_are_present(self) -> None:
        # the plan's §4 candidate axes must all be represented
        for c in ("classification", "valuation", "input_tax_credit",
                  "rate_and_exemption", "procedure_and_limitation"):
            assert c in dc.CAUSES, c


class TestClassify:
    def test_tags_from_the_issue_text(self) -> None:
        assert "classification" in dc.classify(
            "Whether Resin Statues are classifiable under HSN 97030090", "")

    def test_tags_from_a_cited_provision(self) -> None:
        # no useful keywords in the issue, but s.17(5) carries the cause
        assert "input_tax_credit" in dc.classify("Whether the tax is available", "SGST s.17(5)")

    def test_the_act_prefix_does_not_block_a_provision_match(self) -> None:
        # s.16 and SGST s.16 must both be recognised
        assert "input_tax_credit" in dc.classify("Whether credit may be taken", "CGST s.16")

    def test_multi_label_is_intentional(self) -> None:
        # a composite supply's valuation is genuinely both causes
        tags = dc.classify("Whether supply of goods with installation is composite "
                           "or mixed supply and how it is valued", "")
        assert "composite_or_mixed" in tags

    def test_an_unrelated_issue_is_not_force_tagged(self) -> None:
        assert dc.classify("The applicant seeks a clarification", "") == []

    def test_empty_input_is_safe(self) -> None:
        assert dc.classify("", "") == []
        assert dc.classify(None, None) == []


class TestCleanSignal:
    """The first version used str.strip("\\\\b^$"), which removes those CHARACTERS
    from both ends — "\\\\bblocked credit\\\\b" rendered as "locked credit" and
    "maintainab" as "maintaina", so the published draft looked like it had typos."""

    def test_anchors_are_removed(self) -> None:
        assert dc.clean_signal(r"\bHSN\b") == "HSN"

    def test_leading_characters_are_not_eaten(self) -> None:
        assert dc.clean_signal(r"\bblocked credit\b") == "blocked credit"

    def test_trailing_characters_are_not_eaten(self) -> None:
        assert dc.clean_signal(r"\bmaintainab\b") == "maintainab"

    def test_whitespace_classes_are_shown_readably(self) -> None:
        assert dc.clean_signal(r"\bschedule\s+III\b") == "schedule III"

    def test_a_plain_signal_is_unchanged(self) -> None:
        assert dc.clean_signal("HSN") == "HSN"

    def test_every_published_signal_has_no_regex_artefacts(self) -> None:
        for cause, spec in dc.CAUSES.items():
            for s in spec["text"]:
                shown = dc.clean_signal(s)
                assert "\\" not in shown, (cause, shown)
                assert "{" not in shown, (cause, shown)
