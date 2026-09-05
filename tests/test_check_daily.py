def test_diff_listings_finds_new_urls():
    from gst_aar_law_shim import check_daily as cd

    old = [{"source_url": "https://cbic-gst.gov.in/pdf/a.pdf"}]
    new = old + [{"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]
    assert cd.diff_listings(old, new) == [
        {"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]
