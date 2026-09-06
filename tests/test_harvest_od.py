"""Pins for the Odisha harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_od

FIXTURE = """
<table><tr><th>Title</th><th>Date</th><th>File</th></tr>
<tr><td>Finance Deptt 4000</td><td>12-10-2025</td>
<td><a href="/sites/default/files/2025-10/4000%20FINANCE%20%20Deptt.pdf">PDF</a></td></tr>
</table>
<a href="?page=1">2</a><a href="?page=30">last</a>
"""


class TestOdParse:
    def test_rows_and_max_page(self) -> None:
        rows, max_page = harvest_od.parse_page(FIXTURE, "https://finance.odisha.gov.in/en/notification/gst")
        assert max_page == 30
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://finance.odisha.gov.in/sites/default/files/2025-10/4000%20FINANCE%20%20Deptt.pdf")
        assert "Finance Deptt 4000" in rows[0]["cells"]

    def test_no_table(self) -> None:
        assert harvest_od.parse_page("<html>empty</html>", "https://x/") == ([], 0)
