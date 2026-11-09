"""Pins for the Andhra Pradesh harvester (offline fixtures)."""
from __future__ import annotations

from gst_aar_law_shim import harvest_ap

# Trimmed from a live goir.ap.gov.in result page (2026-09-12): the row link is
# javascript:downloadFile("<gid>","E"), not an href.
AP_FIXTURE = """
<table id="FileMoveList2">
<tr><th>S.No</th><th>G.O No</th><th>Date</th><th>G.O Category</th>
    <th>Abstract</th><th>Organization</th><th>Department</th><th>Amount</th><th>File</th></tr>
<tr>
  <td>1</td><td>RT-1610</td><td>11/09/2026</td><td>Service Matter</td>
  <td>Revenue (Commercial Taxes) Department- Medical Reimbursement claim of Smt.V.Lalitha Devi, DCTO(Retd.) - Orders - Issued.</td>
  <td>REV01 - REVENUE</td><td>COMMERCIAL-TAXES</td><td>27000</td>
  <td><a href='javascript:downloadFile("585396", "E");'><i class='fa fa-download'></i></a></td>
  <td><img src='Images/NA.png' alt='Not Available' /></td>
</tr>
<tr>
  <td>2</td><td>G.O.Ms.No.123</td><td>12/06/2017</td><td>Notifications</td>
  <td>Andhra Pradesh Goods and Services Tax Act, 2017 - Notified - Orders - Issued.</td>
  <td>REV01 - REVENUE</td><td>COMMERCIAL-TAXES</td><td>0</td>
  <td><a href='javascript:downloadFile("111222", "E");'></a></td>
  <td><img src='Images/NA.png' alt='Not Available' /></td>
</tr>
<tr><td>3</td><td>no-file row</td></tr>
</table>
"""


class TestApParse:
    def test_parses_gid_and_filetype_from_download_file_js(self) -> None:
        rows = harvest_ap.parse_rows(AP_FIXTURE)
        assert [r["gid"] for r in rows] == ["585396", "111222"]
        assert all(r["file_type"] == "E" for r in rows)

    def test_row_without_download_link_is_skipped(self) -> None:
        assert len(harvest_ap.parse_rows(AP_FIXTURE)) == 2

    def test_cells_carry_go_number_and_date(self) -> None:
        rows = harvest_ap.parse_rows(AP_FIXTURE)
        assert rows[1]["cells"][1] == "G.O.Ms.No.123"
        assert rows[1]["cells"][2] == "12/06/2017"

    def test_empty_page_gives_no_rows(self) -> None:
        assert harvest_ap.parse_rows("<html>no results</html>") == []


class TestApGstFilter:
    def test_service_matter_is_not_gst_law(self) -> None:
        rows = harvest_ap.parse_rows(AP_FIXTURE)
        assert harvest_ap.is_gst(rows[0]) is False

    def test_gst_act_notification_is_kept(self) -> None:
        rows = harvest_ap.parse_rows(AP_FIXTURE)
        assert harvest_ap.is_gst(rows[1]) is True

    def test_vat_term_is_recognised(self) -> None:
        assert harvest_ap.is_gst({"gid": "1", "file_type": "E",
                                  "cells": ["x", "G.O.Ms.No.9", "01/01/2006",
                                            "Andhra Pradesh Value Added Tax rules notified"]})

    def test_search_terms_and_year_window(self) -> None:
        assert "GST" in harvest_ap.SEARCH_TERMS
        assert harvest_ap.FIRST_YEAR == 2017
