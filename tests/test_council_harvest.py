def test_council_link_filter_keeps_gov_in_pdfs():
    from gst_aar_law_shim import harvest_council_gazette as cg

    html = ('<a href="https://gstcouncil.gov.in/sites/default/files/rec-55th.pdf">55th meeting</a>'
            '<a href="https://example.com/x.pdf">outside</a>')
    rows = cg.parse_links(html, "https://gstcouncil.gov.in/")
    assert [r["pdf_url"] for r in rows] == [
        "https://gstcouncil.gov.in/sites/default/files/rec-55th.pdf"]
