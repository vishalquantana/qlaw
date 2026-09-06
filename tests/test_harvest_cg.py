"""Pins for the Chhattisgarh harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_cg

FIXTURE = """
<a href="../pages/Important/GST Refund-98_2024.pdf">refund</a>
<a href="../pages/Important/Sthayi Nirdesh No. 101-2024.pdf">hindi order</a>
<a href="https://comtax.cg.nic.in/2024.htm">2024</a>
"""


class TestCgParse:
    def test_gst_filter_and_subs(self) -> None:
        rows, subs = harvest_cg.parse_hub(FIXTURE, "https://comtax.cg.nic.in/Circ1.htm")
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://comtax.cg.nic.in/pages/Important/GST%20Refund-98_2024.pdf")
        assert subs == ["https://comtax.cg.nic.in/2024.htm"]

    def test_empty(self) -> None:
        assert harvest_cg.parse_hub("<html>empty</html>", "https://x/") == ([], [])
