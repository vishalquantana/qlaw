"""Pins for the CGST Rules splitter.

Two behaviours here are easy to get wrong and were both wrong on the first pass:
the monotonic filter that rejects table rows, and carrying the rule text that
begins on the same line as its heading.
"""
from __future__ import annotations

from gst_aar_law_shim import harvest_cgst_rules as cr

# Rule 7 contains a numbered table; a naive heading regex reads its rows as rules.
SAMPLE = """\
1. Short title and Commencement.- (1) These rules may be called the CGST Rules.
(2) They shall come into force on 22nd June, 2017.
2. Definitions.- In these rules, unless the context otherwise requires,-
7. Rate of tax of the composition levy.- The category of registered persons
shall be as specified in the Table below.
1. Manufacturers, other than manufacturers of such goods
2. Suppliers making supplies referred to in clause (b)
3. Any other supplier eligible for composition levy
8. Application for registration.- (1) Every person shall apply.
"""


class TestSplitRules:
    def test_parses_every_rule(self) -> None:
        rules = cr.split_rules(SAMPLE)
        assert [r["number"] for r in rules] == ["1", "2", "7", "8"]

    def test_table_rows_are_not_treated_as_rules(self) -> None:
        # the 1./2./3. inside Rule 7 restart numbering, so the monotonic walk drops them
        nums = [r["number"] for r in cr.split_rules(SAMPLE)]
        assert nums.count("1") == 1 and nums.count("2") == 1

    def test_inline_text_after_the_heading_is_kept(self) -> None:
        # "(1) These rules may be called..." sits on the heading line
        r1 = cr.split_rules(SAMPLE)[0]
        assert "These rules may be called" in r1["text"]
        assert "22nd June, 2017" in r1["text"]

    def test_title_stops_at_the_dash_marker(self) -> None:
        r1 = cr.split_rules(SAMPLE)[0]
        assert r1["title"] == "Short title and Commencement"
        assert "These rules" not in r1["title"]

    def test_text_continues_onto_following_lines(self) -> None:
        r7 = [r for r in cr.split_rules(SAMPLE) if r["number"] == "7"][0]
        assert "Table below" in r7["text"]

    def test_numbering_letters_are_supported(self) -> None:
        rules = cr.split_rules("10. Issue of registration certificate.- (1) A.\n"
                               "10A. Furnishing of Bank Account Details.- (1) B.\n"
                               "11. Separate registration.- (1) C.\n")
        assert [r["number"] for r in rules] == ["10", "10A", "11"]

    def test_empty_input_yields_nothing(self) -> None:
        assert cr.split_rules("") == []
