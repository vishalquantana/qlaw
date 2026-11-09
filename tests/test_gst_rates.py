"""Pins for the CBIC rate-schedule parser, the rate lookup, and India Code helpers."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import harvest_gst_rates as gr
from gst_aar_law_shim import harvest_indiacode as ic
from gst_aar_law_shim import law_search

GOODS_HTML = """
<table id="goods_table">
<tr><th>Schedules</th><th>S. No.</th><th>Chapter / Heading / Sub-heading</th>
<th>Description of Goods</th><th>CGST Rate (%)</th><th>SGST / UTGST Rate (%)</th>
<th>IGST Rate (%)</th><th>Compensation Cess</th></tr>
<tr><td>I</td><td>7</td><td>0401</td><td>Ultra High Temperature (UHT) milk</td>
<td>2.5%</td><td>2.5%</td><td>5%</td><td></td></tr>
<tr><td>III</td><td>400</td><td>8703</td><td>Motor vehicles</td>
<td>9%</td><td>9%</td><td>18%</td><td>1%</td></tr>
<tr><td>I</td><td>3</td><td>&nbsp;</td><td>[Omitted]</td>
<td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>
"""

SERVICE_HTML = """
<table id="service_table">
<tr><th>S. No.</th><th>Chapter, Section or Heading</th><th>Description of Service</th>
<th>CGST Rate(%)</th><th>SGST/UTGST Rate(%)</th><th>IGST Rate(%)</th><th>Condition</th></tr>
<tr><td>(1)</td><td>(2)</td><td>(3)</td><td>(4)</td><td>(5)</td></tr>
<tr><td>3</td><td>Heading 9954 (Construction)</td><td>Construction of affordable residential apartments</td>
<td>0.75</td><td>0.75</td><td>1.5</td><td>Provided that...</td></tr>
<tr><td>12</td><td>Heading 9968</td><td>Postal and courier services.</td>
<td>9</td><td>9</td><td>18</td><td></td></tr>
</table>
"""


class TestRateParsing:
    def test_goods_rows_parsed(self) -> None:
        rows = gr.parse_table(GOODS_HTML, "goods_table")
        assert rows[0][0] == "Schedules"          # header preserved
        assert rows[1][:4] == ["I", "7", "0401", "Ultra High Temperature (UHT) milk"]
        assert len(rows) == 4

    def test_service_rows_parsed(self) -> None:
        rows = gr.parse_table(SERVICE_HTML, "service_table")
        assert rows[2][0] == "3"
        assert rows[2][1] == "Heading 9954 (Construction)"
        assert len(rows) == 4

    def test_missing_table_is_empty(self) -> None:
        assert gr.parse_table("<html></html>", "goods_table") == []


class TestRateNormalisation:
    def test_percent_is_kept(self) -> None:
        assert gr.norm_rate("2.5%") == "2.5%"

    def test_bare_number_gets_a_percent_sign(self) -> None:
        assert gr.norm_rate("9") == "9%"

    def test_blank_stays_blank(self) -> None:
        # an [Omitted] row has no rate; it must not become "0%"
        assert gr.norm_rate("") == ""
        assert gr.norm_rate("   ") == ""

    def test_nil_is_preserved_as_text(self) -> None:
        assert gr.norm_rate("Nil") == "Nil"


class TestCodeExtraction:
    def test_single_code(self) -> None:
        assert gr.codes_in("0401") == ["0401"]

    def test_comma_list_is_exploded(self) -> None:
        assert gr.codes_in("0202, 0203, 0204") == ["0202", "0203", "0204"]

    def test_heading_text_yields_its_number(self) -> None:
        assert gr.codes_in("Heading 9954 (Construction)") == ["9954"]

    def test_any_chapter_yields_nothing(self) -> None:
        assert gr.codes_in("Any chapter") == []
        assert gr.codes_in("") == []


class TestRateLookupCli:
    """The lookup the CLI and /api/rate share."""

    def _con(self):
        con = sqlite3.connect(":memory:")
        con.executescript(gr.SCHEMA)
        con.execute(
            "INSERT INTO rate_facts (id, kind, schedule, sr_no, hsn_sac, description,"
            " cgst_rate, sgst_rate, igst_rate, source_url)"
            " VALUES (1,'goods','I','7','0401','Ultra High Temperature (UHT) milk',"
            "'2.5%','2.5%','5%','https://cbic-gst.gov.in/x')")
        con.execute("INSERT INTO rate_codes (code,kind,fact_id) VALUES ('0401','goods',1)")
        con.execute(
            "INSERT INTO rate_facts (id, kind, schedule, sr_no, hsn_sac, description,"
            " cgst_rate, igst_rate, source_url)"
            " VALUES (2,'goods','II','5','0402 91 10, 0402 99 20','Condensed milk',"
            "'6%','12%','https://cbic-gst.gov.in/x')")
        con.execute("INSERT INTO rate_codes (code,kind,fact_id) VALUES ('0402','goods',2)")
        con.commit()
        return con

    def test_lookup_by_code_finds_the_line(self, capsys) -> None:
        n = law_search.show_rate(self._con(), "0401", 10)
        out = capsys.readouterr().out
        assert n == 1
        assert "2.5%" in out and "UHT" in out

    def test_lookup_reports_a_code_it_does_not_hold(self, capsys) -> None:
        assert law_search.show_rate(self._con(), "9999", 10) == 0
        assert "no rate line" in capsys.readouterr().out

    def test_a_grouped_cell_is_reachable_by_one_of_its_codes(self) -> None:
        # the source groups codes; rate_codes explodes them so 0402 works
        assert law_search.show_rate(self._con(), "0402", 10) == 1

    def test_description_search(self, capsys) -> None:
        n = law_search.show_rate_search(self._con(), "milk", 10)
        out = capsys.readouterr().out
        assert n == 2
        assert "0401" in out and "0402" in out

    def test_description_search_with_no_match(self, capsys) -> None:
        assert law_search.show_rate_search(self._con(), "zzzz", 10) == 0
        assert "no rate line" in capsys.readouterr().out


class TestIndiaCodeHelpers:
    def test_norm_strips_leading_the_and_punctuation(self) -> None:
        assert ic.norm("The Central Goods and Services Tax Act, 2017") == (
            "central goods and services tax act 2017")
        assert ic.norm("Customs Act, 1962") == "customs act 1962"

    def test_norm_matches_the_two_sources(self) -> None:
        # CBIC title vs India Code title for the same Act
        assert ic.norm("Customs Act, 1962") == ic.norm("The Customs Act, 1962")

    def test_clean_text_strips_html(self) -> None:
        t = ic.clean_text("<p>Levy and collection</p><span style='x'>of tax</span>")
        assert "Levy and collection" in t
        assert "<" not in t and ">" not in t

    def test_clean_text_decodes_entities(self) -> None:
        assert "&" in ic.clean_text("levy &amp; collection")
