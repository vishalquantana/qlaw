"""Pins for the Assam harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_as

FIXTURE = """
<tr bgcolor="#ffffff">
<td><div align="center">  1.</div></td>
<td>Notification No.1/2017-GST &nbsp;&nbsp;&nbsp; CT/GST-10/2017/185 dtd.07/08/2017</td>
<td width="100%"><div align="left"><a href="../GST/FORMATS/No_469_CT_GST_10_2017_185.pdf" target="_blank">Time Period for filing FORM GSTR-1.</a></div></td>
</tr>
"""


class TestAsParse:
    def test_rows_and_relative_urls(self) -> None:
        rows = harvest_as.parse_table(
            FIXTURE, "https://tax.assam.gov.in/AssamTimsInfo/content/GST_Notifications_COT.html")
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://tax.assam.gov.in/AssamTimsInfo/GST/FORMATS/No_469_CT_GST_10_2017_185.pdf")
        assert "Notification No.1/2017-GST" in rows[0]["cells"][1]

    def test_no_rows(self) -> None:
        assert harvest_as.parse_table("<html>empty</html>", "https://x/") == []
