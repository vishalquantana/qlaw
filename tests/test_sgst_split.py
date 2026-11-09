"""Pins for the State GST Act splitter.

The important behaviour here is what the splitter REFUSES to do. The state Acts come
in at least four gazette layouts, and only one of them splits with a single pattern.
A tool that silently stored a handful of stray "sections" for the other 73 would look
like coverage while being useless, so the guard and the layout report are the point.
"""
from __future__ import annotations

from gst_aar_law_shim import split_sgst_acts as ss

# the Goa layout: heading and text on one run, terminated by an em-dash
GOA_STYLE = (
    "CHAPTER I Preliminary "
    "1. Short title, extent and commencement.\u2014 (1) This Act may be called the Goa "
    "Goods and Services Tax Act, 2017. (2) It extends to the whole of Goa. "
    "2. Definitions.\u2014 In this Act, unless the context otherwise requires, "
    "3. Officers under this Act.\u2014 The Government shall appoint officers. "
    # a trailing amendment table whose entries also look numbered
    "1. Inserted vide Amendment Act 9 of 2025. 2. Inserted vide Amendment Act 4 of 2019."
)

MARGINAL_STYLE = (
    "\n \n\n CHAPTER I \n\nPRELIMINARY \n\n \n\n 1. (1) This Act may be called the "
    "Tripura State Goods and Services Tax Act, 2017; \nShort title, extent \n\nand "
    "\n\ncommencement. \n\n (2) It extends to the whole of the Tripura;"
)

ARRANGEMENT_STYLE = (
    "ARRANGEMENT OF SECTIONS (ACT No.16 of 2017) SECTIONS CHAPTER I PRELIMINARY "
    "1. Short title, extent and commencement 2. Definitions 3. Officers under this Act"
)


class TestFlatten:
    def test_blank_line_layout_is_collapsed(self) -> None:
        # the real text separates every visual line with a blank line
        assert ss.flatten("a \n\n b \n\n c") == "a b c"

    def test_empty_input(self) -> None:
        assert ss.flatten("") == ""


class TestSplitAct:
    def test_finds_the_sections(self) -> None:
        secs = ss.split_act(GOA_STYLE)
        assert [s["number"] for s in secs] == ["1", "2", "3"]

    def test_titles_are_clean(self) -> None:
        secs = ss.split_act(GOA_STYLE)
        assert secs[0]["title"] == "Short title, extent and commencement"

    def test_section_text_is_captured(self) -> None:
        secs = ss.split_act(GOA_STYLE)
        assert "may be called the Goa" in secs[0]["text"]

    def test_the_trailing_amendment_table_is_rejected(self) -> None:
        # its entries restart at 1, so the monotonic walk drops them
        nums = [s["number"] for s in ss.split_act(GOA_STYLE)]
        assert nums.count("1") == 1 and nums.count("2") == 1

    def test_marginal_note_layout_yields_nothing(self) -> None:
        # deliberately: this layout needs column-aware extraction, and guessing
        # would produce junk sections
        assert ss.split_act(MARGINAL_STYLE) == []

    def test_empty_input_yields_nothing(self) -> None:
        assert ss.split_act("") == []


class TestClassify:
    def test_inline_heading_when_it_parses(self) -> None:
        assert ss.classify(GOA_STYLE, 169) == "inline heading"

    def test_marginal_note_is_detected(self) -> None:
        assert ss.classify(MARGINAL_STYLE, 0) == "marginal note"

    def test_arrangement_index_is_detected(self) -> None:
        assert ss.classify(ARRANGEMENT_STYLE, 0) == "arrangement index only"

    def test_unrecognised_is_reported_rather_than_guessed(self) -> None:
        assert ss.classify("some other gazette layout entirely", 0) == "unrecognised"

    def test_a_full_parse_beats_the_index_heuristic(self) -> None:
        # an Act that both has an index and parses is classified by the parse
        text = ARRANGEMENT_STYLE + " " + GOA_STYLE
        assert ss.classify(text, 150) == "inline heading"


class TestGuard:
    def test_the_threshold_is_meaningful(self) -> None:
        # the CGST Act has 174 sections; anything far below that is not a parse
        assert 100 <= ss.MIN_PLAUSIBLE <= 174

    def test_a_goa_scale_parse_clears_it(self) -> None:
        assert len(ss.split_act(GOA_STYLE)) < ss.MIN_PLAUSIBLE  # tiny fixture
