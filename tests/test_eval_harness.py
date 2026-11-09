"""Pins for the evaluation harness.

The resolvability check is the subtle part. Its first version keyed on the section
number alone and reported 67% — a misleading figure, because 161 of 174 section
numbers are shared between Acts, so "s.98" matched the Customs Act's section 98 as
readily as the CGST Act's. Keying on (Act, number) gives the true picture.
"""
from __future__ import annotations

from gst_aar_law_shim import eval_harness as eh


class TestBaseSection:
    def test_strips_the_sub_clause(self) -> None:
        assert eh.base_section("98(4)") == "98"
        assert eh.base_section("2(30)") == "2"

    def test_keeps_letter_suffixes(self) -> None:
        assert eh.base_section("11A(2)") == "11A"
        assert eh.base_section("10A") == "10A"

    def test_handles_a_bare_number(self) -> None:
        assert eh.base_section("36") == "36"

    def test_returns_empty_for_junk(self) -> None:
        assert eh.base_section("") == ""
        assert eh.base_section("(4)") == ""


class TestActMapping:
    def test_each_prefix_maps_to_a_distinct_act(self) -> None:
        acts = list(eh.ACT_FOR_PREFIX.values())
        assert len(acts) == len(set(acts)) == 3

    def test_the_gst_acts_are_the_ones_mapped(self) -> None:
        # NB the Acts are titled inconsistently — "Goods and Services Tax" for CGST
        # but "Goods And Services Tax" for IGST and UTGST — so compare case-insensitively
        for act in eh.ACT_FOR_PREFIX.values():
            assert "goods and services tax" in act.lower(), act

    def test_sgst_is_not_mapped_to_a_central_act(self) -> None:
        # State Acts are not held as sections; mapping them to CGST would be a
        # legal claim the check should not make silently
        assert "SGST" not in eh.ACT_FOR_PREFIX
        assert "SGST" in eh.STATE_PREFIXES


class TestSectionIdPattern:
    def test_parses_a_citation(self) -> None:
        m = eh.SECTION_ID.match("SGST s.98(4)")
        assert m is not None
        assert m.group(1).upper() == "SGST" and m.group(2) == "98(4)"

    def test_parses_a_central_citation(self) -> None:
        m = eh.SECTION_ID.match("CGST s.17(5)")
        assert m is not None and m.group(1).upper() == "CGST"

    def test_rejects_a_non_citation(self) -> None:
        assert eh.SECTION_ID.match("section 98 of the Act") is None


class TestLabelSheet:
    def test_the_label_columns_are_present(self) -> None:
        for col in ("ruling_id", "issue", "provisions_we_found",
                    "issue_ok", "provisions_ok", "outcome_ok", "rate_ok", "notes"):
            assert col in eh.LABEL_COLUMNS

    def test_the_reviewer_columns_come_last(self) -> None:
        # so a reviewer scrolls right to the empty cells and fills them
        tail = eh.LABEL_COLUMNS[-5:]
        assert tail == ["issue_ok", "provisions_ok", "outcome_ok", "rate_ok", "notes"]
