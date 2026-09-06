"""Pins for Karnataka / UP / Tamil Nadu harvesters (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_ka, harvest_tn, harvest_up

KA_FIXTURE = """
<table><tr><th>Sl</th><th>Subject</th><th>No</th><th>Date</th><th>Doc</th></tr>
<tr><td>56</td><td>GSTAT Proceedings auth reps</td><td>No. FD 34 CSL 2026</td>
<td>16/07/2026</td><td><a href="latestupdates/GSTATProceedings16072026.pdf">View</a></td></tr>
<tr><td>text-only row without a file</td></tr>
</table>
"""

UP_HUB_FIXTURE = """
<a href="notification/2025-26/notice1.html">2025-26</a>
<a href="notification/2024-25/notice1.html">2024-25</a>
"""

UP_YEAR_FIXTURE = """
<table><tr><th>Sl</th><th>Doc</th><th>Date</th><th>Subject</th></tr>
<tr><td>1</td><td><a href="../2025-26/English/noti_no_3487eng17-04-2025.pdf">Noti_no_348</a>
/ <a href="../2025-26/Hindi/noti_no_348hindi17-04-2025.pdf">Noti_no_348</a></td>
<td>17-04-2025</td><td>U.P. GST Rules Order 348</td></tr>
</table>
"""

TN_PAYLOAD = {"files": [
    {"name": "TN Gazette No.21 & Dated: 27-05-2026", "date": "27/05/2026",
     "description": "TN Gazette No.21", "adminFileId": "VdrowaPL6M0cwjUuDyUCCw==",
     "fileType": "pdf"},
    {"name": "no-id row", "date": "01/01/2020", "description": "skipped"},
]}


class TestKaParse:
    def test_rows_and_relative_urls(self) -> None:
        rows = harvest_ka.parse_table(KA_FIXTURE, "https://gst.karnataka.gov.in/x.aspx")
        assert len(rows) == 1
        assert rows[0]["pdf_url"] == (
            "https://gst.karnataka.gov.in/latestupdates/GSTATProceedings16072026.pdf")
        assert any("FD 34 CSL 2026" in c for c in rows[0]["cells"])

    def test_no_table_gives_no_rows(self) -> None:
        assert harvest_ka.parse_table("<html>empty</html>", "https://x/") == []


class TestUpParse:
    def test_hub_newest_first(self) -> None:
        years = harvest_up.parse_hub(UP_HUB_FIXTURE,
                                     "https://comtax.up.nic.in/GSThome/en/gst-notification.html")
        assert years == [
            "https://comtax.up.nic.in/GSThome/en/notification/2025-26/notice1.html",
            "https://comtax.up.nic.in/GSThome/en/notification/2024-25/notice1.html"]

    def test_clean_encodes_spaces(self) -> None:
        u = harvest_up.clean("https://comtax.up.nic.in/a b/c d.pdf")
        assert " " not in u and u.endswith("a%20b/c%20d.pdf")

    def test_year_twins(self) -> None:
        rows = harvest_up.parse_year(
            UP_YEAR_FIXTURE,
            "https://comtax.up.nic.in/GSThome/en/notification/2025-26/notice1.html")
        assert len(rows) == 2
        urls = [r["pdf_url"] for r in rows]
        assert urls[0] == ("https://comtax.up.nic.in/GSThome/en/notification/"
                           "2025-26/English/noti_no_3487eng17-04-2025.pdf")
        assert urls[1].endswith("/Hindi/noti_no_348hindi17-04-2025.pdf")
        assert any("17-04-2025" in c for c in rows[0]["cells"])


class TestTnParse:
    def test_files_and_download_url(self) -> None:
        rows = harvest_tn.parse_files(TN_PAYLOAD)
        assert len(rows) == 1  # no-id row skipped
        assert rows[0]["pdf_url"].startswith(
            "https://tnvat.tn.gov.in/ctdportal/DownloadServlet?fileId=")
        assert "%3D%3D" in rows[0]["pdf_url"]  # base64 == encoded
        assert "27/05/2026" in rows[0]["cells"]

    def test_empty_payload(self) -> None:
        assert harvest_tn.parse_files({}) == []
        assert harvest_tn.parse_files({"files": []}) == []
