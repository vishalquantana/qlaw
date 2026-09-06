"""Pins for the Telangana harvester (offline: fixture GridView HTML)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_tgct

FIXTURE = """
<table id="ctl00_ContentPlaceHolder1_gvGSTFilesBind">
<tr><th>S.No</th><th>No</th><th>Date</th><th>State</th><th>CBIC</th></tr>
<tr><td>1</td><td>13/2025</td><td>17-09-2025</td>
<td><a href="javascript:__doPostBack(&#39;ctl00$ContentPlaceHolder1$gvGSTFilesBind$ctl02$lblCSTNoteNo&#39;,&#39;&#39;)">G.O. 123</a></td>
<td><a href="javascript:__doPostBack(&#39;ctl00$ContentPlaceHolder1$gvGSTFilesBind$ctl02$lblCibicNoteNo&#39;,&#39;&#39;)">CBIC</a></td></tr>
</table>
<input type="hidden" name="__VIEWSTATE" value="AAA" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="BBB" />
<input type="hidden" name="__EVENTVALIDATION" value="CCC" />
"""


class TestParseGrid:
    def test_rows_cells_targets(self) -> None:
        rows = harvest_tgct.parse_grid(FIXTURE)
        assert len(rows) == 1
        assert rows[0]["cells"][:3] == ["1", "13/2025", "17-09-2025"]
        assert rows[0]["targets"] == [
            "ctl00$ContentPlaceHolder1$gvGSTFilesBind$ctl02$lblCSTNoteNo",
            "ctl00$ContentPlaceHolder1$gvGSTFilesBind$ctl02$lblCibicNoteNo",
        ]

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_tgct.parse_grid("<html>empty</html>") == []


class TestHiddenFields:
    def test_extracts_all_three(self) -> None:
        f = harvest_tgct.hidden_fields(FIXTURE)
        assert f == {"__VIEWSTATE": "AAA", "__VIEWSTATEGENERATOR": "BBB",
                     "__EVENTVALIDATION": "CCC"}

    def test_missing_gives_empty(self) -> None:
        assert harvest_tgct.hidden_fields("<html/>")["__VIEWSTATE"] == ""
