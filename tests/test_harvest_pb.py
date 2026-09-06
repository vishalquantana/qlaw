"""Pins for the Punjab harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_pb

FIXTURE = """
<a href="/attachments/attachment0012834020520231683014314_GST Update March 2023 (1).pdf">u</a>
<a href="/attachments/attachment0110659311020201604165819_GSTCALENDAR.pdf">c</a>
<a href="/attachments/attachment0111540311020201604166340_INST CALENDER.pdf">non-gst</a>
<a href="/products/content/23">sub-page</a>
"""


class TestPbParse:
    def test_gst_filter_and_pages(self) -> None:
        rows, pages = harvest_pb.parse_attachments(FIXTURE, "https://taxation.punjab.gov.in/")
        urls = [r["pdf_url"] for r in rows]
        assert len(rows) == 2
        assert all("gst" in u.lower() for u in urls)
        assert "/products/content/23" in pages

    def test_empty(self) -> None:
        assert harvest_pb.parse_attachments("<html>empty</html>", "https://x/") == ([], [])
