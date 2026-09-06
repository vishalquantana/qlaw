"""Pins for Haryana GST harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_hr

HR_FIXTURE = """
<table><tr><th>GST</th><th>Action</th></tr>
<tr><td>22nd July, 2026No.08/GST-2&#xA0;GSTAT appeal time-limit extension</td>
<td><a href="https://haryanatax.gov.in//Website_Content_Files/AmendmentsNotifications/AmendmentsNotifications/GST/GST%20NotificationAmendment/2026/22nd_July_2026/8_Notifications_GST_2026.pdf">Download</a></td></tr>
<tr><td>same file linked again</td>
<td><a href="https://haryanatax.gov.in//Website_Content_Files/AmendmentsNotifications/AmendmentsNotifications/GST/GST%20NotificationAmendment/2026/22nd_July_2026/8_Notifications_GST_2026.pdf">Download</a></td></tr>
<tr><td>text-only row without a file</td></tr>
</table>
"""


class TestHrParse:
    def test_rows_deduped_and_urls_kept(self) -> None:
        rows = harvest_hr.parse_table(
            HR_FIXTURE, "https://haryanatax.gov.in/LoadPartial/x")
        assert len(rows) == 1  # repeat href collapses to one row
        assert rows[0]["pdf_url"] == (
            "https://haryanatax.gov.in//Website_Content_Files/AmendmentsNotifications/"
            "AmendmentsNotifications/GST/GST%20NotificationAmendment/2026/"
            "22nd_July_2026/8_Notifications_GST_2026.pdf")
        assert any("08/GST-2" in c for c in rows[0]["cells"])

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_hr.parse_table("<html>empty</html>", "https://x/") == []
