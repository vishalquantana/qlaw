"""Pins for the Maharashtra harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_mh

FIXTURE = """
<table><tr><th>Sr</th><th>Date</th><th>No</th><th>Subject</th><th>PDF</th></tr>
<tr><td class="text-center">1</td><td class="text-center">07/07/2026</td>
<td>MAHARASHTRA ACT No. XXVII of 2026</td><td>MGST Amendment Act</td>
<td><a href="https://www.mahagst.gov.in/public/uploads/mvatservices/1784876839_MGST-Amend.pdf">PDF</a></td></tr>
<tr><td>no-pdf row</td></tr>
</table>
<a href="https://www.mahagst.gov.in/en/gst-notifications-mgst?page=12">last</a>
"""


class TestMhParse:
    def test_rows_and_max_page(self) -> None:
        rows, max_page = harvest_mh.parse_page(
            FIXTURE, "https://www.mahagst.gov.in/en/gst-notifications-mgst")
        assert max_page == 12
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://www.mahagst.gov.in/public/uploads/mvatservices/1784876839_MGST-Amend.pdf")
        assert "07/07/2026" in rows[0]["cells"]

    def test_no_table(self) -> None:
        assert harvest_mh.parse_page("<html>empty</html>", "https://x/") == ([], 0)

    def test_spaces_quoted(self) -> None:
        assert harvest_mh.clean_url("https://x/a b,c.pdf") == "https://x/a%20b%2Cc.pdf"
