"""Pins for shared HTTPS helper + West Bengal harvester (offline fixtures)."""
from __future__ import annotations

import ssl

from gst_aar_law_shim import _https, harvest_wb

WB_FIXTURE = """
<table><tr><th>No</th><th>Date</th><th>Subject</th><th>Doc</th></tr>
<tr><td>1225-FT</td><td>22-07-2026</td><td>Rate amendment</td>
<td><a href="Notification_1225FT_20260722.pdf">PDF</a></td></tr>
<tr><td>text-only row without a file</td></tr>
</table>
"""


class TestHttps:
    def test_legacy_renegotiation_enabled(self) -> None:
        if getattr(ssl, "OP_LEGACY_SERVER_CONNECT", None) is None:
            return  # old OpenSSL without the flag — nothing to assert
        assert _https.context().options & ssl.OP_LEGACY_SERVER_CONNECT

    def test_session_opens(self) -> None:
        assert _https.session() is not None


class TestWbParse:
    def test_rows_and_relative_urls(self) -> None:
        rows = harvest_wb.parse_table(
            WB_FIXTURE, "https://comtax.wb.gov.in/GST/GST_Notifications/x.html")
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://comtax.wb.gov.in/GST/GST_Notifications/Notification_1225FT_20260722.pdf")
        assert "1225-FT" in rows[0]["cells"]

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_wb.parse_table("<html>empty</html>", "https://x/") == []
