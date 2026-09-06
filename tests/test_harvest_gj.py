"""Pins for Gujarat + Rajasthan harvesters (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_gj, harvest_rj

GJ_FIXTURE = """
<table><tr><th>S.No</th><th>Tax Type</th><th>Subject</th></tr>
<tr><td>2</td><td> GST </td><td>Rate</td>
<td><input type="hidden" name="urlOpenList1"
 value="download/cir_noti/NOTI/N-20-2025-ST.pdf"/>
 <a href="javascript:fn_getDetails('137903')">Fifth Amendment Rules, 2025</a></td>
 <td>30/01/2026</td></tr>
<tr><td>1</td><td> VAT </td><td>Rate of TAX</td>
<td><input type="hidden" name="urlOpenList1" value="download/cir_noti/NOTI/vat.pdf"/>
 <a href="javascript:fn_getDetails('137900')">Alcoholic liquor rate</a></td>
 <td>23/06/2026</td></tr>
<tr><td>menu row without hidden input</td></tr>
</table>
"""

RJ_FIXTURE = """
<table>
<tr><td style="white-space:nowrap;"> 1.</td><td>
<a href='../PDFDOCS/TAX/GST/15031.pdf' target='_blank' rel='noopener noreferrer'>Order for
reimbursement of SGST for the hindi film "Bharat Bhhagya Viddhaata"</a><br>
<span class='file-number'>[F.24(3)FD/Tax/2026-04]</span></td>
<td style="white-space:nowrap;">13-Jun-2026</td></tr>
<tr><td>menu row without a pdf link</td></tr>
</table>
"""

RJ_HOME_FIXTURE = """
<form><input type="hidden" name="__VIEWSTATE" value="abc123" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="AB12" />
<input type="hidden" name="__EVENTVALIDATION" value="xyz789" /></form>
"""


class TestGjParse:
    def test_hidden_input_rows_and_quoting(self) -> None:
        rows = harvest_gj.parse_table(GJ_FIXTURE, harvest_gj.BASE)
        assert len(rows) == 2
        assert rows[0]["pdf_url"] == (
            "https://commercialtax.gujarat.gov.in/vatwebsite/"
            "download/cir_noti/NOTI/N-20-2025-ST.pdf")
        assert rows[0]["tax_type"] == "GST"
        assert rows[1]["tax_type"] == "VAT"

    def test_gst_filter(self) -> None:
        rows = harvest_gj.parse_table(GJ_FIXTURE, harvest_gj.BASE)
        assert [harvest_gj.is_gst(r) for r in rows] == [True, False]

    def test_spacey_filename_gets_quoted(self) -> None:
        fix = GJ_FIXTURE.replace("N-20-2025-ST.pdf", "GGST notification 01-2026.pdf")
        rows = harvest_gj.parse_table(fix, harvest_gj.BASE)
        assert "%20" in rows[0]["pdf_url"] and " " not in rows[0]["pdf_url"]

    def test_total_records(self) -> None:
        assert harvest_gj.total_records("Total Records : 939 &nbsp;") == 939

    def test_no_rows_gives_empty(self) -> None:
        assert harvest_gj.parse_table("<html>empty</html>", harvest_gj.BASE) == []


class TestRjParse:
    def test_result_rows_resolve_under_pdfdocs(self) -> None:
        rows = harvest_rj.parse_table(RJ_FIXTURE, harvest_rj.RESULT)
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://finance.rajasthan.gov.in/PDFDOCS/TAX/GST/15031.pdf")
        assert any("15031" in c or "F.24(3)" in c for c in rows[0]["cells"])
        assert any("13-Jun-2026" in c for c in rows[0]["cells"])

    def test_gst_text_match(self) -> None:
        rows = harvest_rj.parse_table(RJ_FIXTURE, harvest_rj.RESULT)
        assert harvest_rj.is_gst(rows[0]) is True

    def test_postback_fields_extracted(self) -> None:
        fields = harvest_rj.extract_postback(RJ_HOME_FIXTURE)
        assert fields["__VIEWSTATE"] == "abc123"
        assert fields["__EVENTVALIDATION"] == "xyz789"
        assert fields["__EVENTTARGET"] == harvest_rj.SECTION_TARGET

    def test_postback_missing_viewstate_raises(self) -> None:
        try:
            harvest_rj.extract_postback("<html>empty</html>")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")

    def test_no_rows_gives_empty(self) -> None:
        assert harvest_rj.parse_table("<html>empty</html>", harvest_rj.BASE
                                      if hasattr(harvest_rj, "BASE") else harvest_rj.HOME) == []
