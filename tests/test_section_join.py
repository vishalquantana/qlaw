"""Pins for the CBIC-to-India Code section join.

The join is mostly a key lookup, but two cases need care and both were added after
real gaps were found: an Act India Code titles differently, and rows the CBIC
hierarchy stored with no Act name at all.
"""
from __future__ import annotations

from gst_aar_law_shim import join_cbic_section_text as jc


class TestNormalisation:
    def test_section_prefix_is_stripped(self) -> None:
        assert jc.norm_section("Section 11A") == "11A"
        assert jc.norm_section("11A") == "11A"

    def test_lettered_sections_survive(self) -> None:
        assert jc.norm_section("Section 11DDA") == "11DDA"
        assert jc.norm_section("Section 154AC") == "154AC"

    def test_act_names_compare_across_the_two_sources(self) -> None:
        assert jc.norm("The Customs Act, 1962") == jc.norm("Customs Act, 1962")
        assert jc.norm("Central Goods And Services Tax Act, 2017") == \
            jc.norm("The Central Goods and Services Tax Act, 2017")


class TestActAliases:
    def test_the_provisional_collection_year_quirk_is_mapped(self) -> None:
        # CBIC says 1931, India Code says 2023 — same Act, section titles match 1:1
        k = jc.norm("Provisional Collection of Taxes Act, 1931")
        assert jc.ACT_ALIASES[k] == jc.norm("Provisional collection of Taxes Act,2023")

    def test_an_unaliased_act_is_looked_up_under_its_own_name(self) -> None:
        k = jc.norm("Customs Act, 1962")
        assert jc.ACT_ALIASES.get(k, k) == k


class TestTitleFallback:
    """Used only where the CBIC row recorded no Act, so the section number alone is
    ambiguous across Acts."""

    def _cands(self):
        return [
            {"section_number": "5", "title": "Export and import policy",
             "act_name": "The Foreign Trade (Development and Regulation) Act, 1992"},
            {"section_number": "5", "title": "Powers of officers of customs",
             "act_name": "The Customs Act, 1962"},
        ]

    def test_picks_the_candidate_whose_heading_overlaps(self) -> None:
        got = jc.pick_by_title(self._cands(), "Section 5 — Export and import policy")
        assert got is not None
        assert "Foreign Trade" in got["act_name"]

    def test_picks_the_other_one_when_the_heading_differs(self) -> None:
        got = jc.pick_by_title(self._cands(), "Section 5 — Powers of officers of customs")
        assert got is not None
        assert "Customs" in got["act_name"]

    def test_a_single_candidate_is_accepted_without_a_heading(self) -> None:
        only = [{"section_number": "3", "title": "Whatever", "act_name": "X"}]
        assert jc.pick_by_title(only, "") == only[0]

    def test_no_overlap_returns_nothing_rather_than_guessing(self) -> None:
        assert jc.pick_by_title(self._cands(), "Section 5 — Something unrelated") is None

    def test_empty_candidate_list(self) -> None:
        assert jc.pick_by_title([], "Section 5 — Anything") is None


class TestBodyProvenance:
    def test_act_name_is_read_from_the_body(self) -> None:
        act, sec = jc.act_and_section(
            "Section: Section 36 — Documentary requirements\n"
            "Act: Central Goods and Services Tax Act, 2017\n", "Section 36")
        assert act == "Central Goods and Services Tax Act, 2017"
        assert sec == "36"

    def test_a_row_with_no_act_yields_an_empty_name(self) -> None:
        act, sec = jc.act_and_section("Section: Section 5 — Export policy\n", "Section 5")
        assert act == ""
        assert sec == "5"
