"""Pins for the Bihar harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_br

SEARCH_FIXTURE = """
<form name="circular" method="post" action="/bweb/circular.do;jsessionid=abc123">
<input type="hidden" name="todayDate" value="06/09/2026" id="todayDate">
<input name="strType" id="strType" type="hidden" value="GSTN">
<input name="strActionType" id="strActionType" type="hidden" value="SEARCH">
</form>
"""

RESULT_FIXTURE = """
<table><tr><th>No</th><th>Subject</th><th>Download</th></tr>
<tr><td>16/2025</td><td>Rate change</td>
<td><a href="/bweb/download/GSTN-16-2025.pdf">Download</a></td></tr>
<tr><td>nav</td><td>x</td><td><a href="/bweb/download/CTDMailList.pdf">mails</a></td></tr>
</table>
"""


class TestBrParse:
    def test_search_page(self) -> None:
        url, fields = harvest_br.search_page(SEARCH_FIXTURE)
        assert "circular.do;jsessionid=abc123" in url
        assert fields["strType"] == "GSTN"
        assert fields["strActionType"] == "SEARCH"
        assert fields["fromDate"] == "01/01/2017"

    def test_results_skip_nav_links(self) -> None:
        rows = harvest_br.parse_results(RESULT_FIXTURE, "https://www.biharcommercialtax.gov.in/bweb/x")
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://www.biharcommercialtax.gov.in/bweb/download/GSTN-16-2025.pdf")
        assert "16/2025" in rows[0]["cells"]
