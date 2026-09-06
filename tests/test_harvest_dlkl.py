"""Pins for Delhi + Kerala GST harvesters (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_dl, harvest_kl

DL_FIXTURE = """
<table><tr><th>S.No</th><th>Number</th><th>Date</th><th>Subject</th><th>Download</th></tr>
<tr><td>1</td><td>No. F.3(33)/Fin/2025</td><td>24-04-2026</td>
<td>Notification Number 16/2024-State Tax</td>
<td><a href="/sites/default/files/dvat/public-notice/notification_number_162024-state.pdf">Download | 411 KB</a></td></tr>
<tr><td>2</td><td>sidebar row</td><td></td><td></td>
<td><a href="/sites/default/files/2023-05/cst_act_1956.pdf">CST Act</a></td></tr>
</table>
<a href="?page=1">next</a><a href="?page=24">last</a>
"""

KL_FIXTURE = """
<div class="entry-content">
<table><tr><td>NO</td><td>Date</td><td>Subject</td></tr>
<tr><td>Notification No.7/2025-State Tax</td><td>28-04-2025</td>
<td>Transportation of Petroleum products</td>
<td><a href="/wp-content/uploads/2017/10/Notification-07-2025.pdf">pdf</a></td></tr>
<tr><td>text-only row without a file</td></tr>
</table>
</div>
<a href="/wp-content/uploads/2025/02/gazette-Notification-RTS_250131_143351.pdf">menu boilerplate</a>
"""


class TestDlParse:
    def test_rows_scoped_to_notice_table_and_max_page(self) -> None:
        rows, max_page = harvest_dl.parse_page(
            DL_FIXTURE, "https://delhitradetax.delhi.gov.in/dvat-notification")
        assert len(rows) == 1  # sidebar cst_act_1956.pdf excluded
        assert rows[0]["pdf_url"] == (
            "https://delhitradetax.delhi.gov.in/sites/default/files/dvat/"
            "public-notice/notification_number_162024-state.pdf")
        assert "16/2024-State Tax" in " ".join(rows[0]["cells"])
        assert max_page == 24

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_dl.parse_page("<html>empty</html>", "https://x/") == ([], 0)


class TestKlParse:
    def test_rows_scoped_to_entry_content(self) -> None:
        rows = harvest_kl.parse_table(
            KL_FIXTURE, "http://www.keralataxes.gov.in/2017/10/25/kgst-notifications/")
        assert len(rows) == 1  # menu boilerplate pdf excluded
        assert rows[0]["pdf_url"] == (
            "http://www.keralataxes.gov.in/wp-content/uploads/2017/10/"
            "Notification-07-2025.pdf")
        assert "7/2025" in " ".join(rows[0]["cells"])

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_kl.parse_table("<html>empty</html>", "https://x/") == []
