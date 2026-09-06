"""Part A: CBIC JSON API harvest — normalize + auth headers."""


def test_parse_act_page_picks_pdf_and_html():
    from gst_aar_law_shim import harvest_cbic_api as api

    page = [{"actId": 1000270, "actName": "Central Goods and Services Tax Act, 2017",
             "contentFilePath": "tax_repository\\gst\\acts\\cgst.pdf",
             "contentHtmlFilePath": "tax_repository/gst/acts/cgst.html",
             "issueDt": "12-Apr-2017", "amendDt": "28-Sep-2022"}]
    docs = api.normalize_acts(page)
    assert docs[0]["title"] == "Central Goods and Services Tax Act, 2017"
    assert docs[0]["source_url"].startswith("https://taxinformation.cbic.gov.in")
    assert docs[0]["kind"] == "act"


def test_auth_headers_carry_bearer():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert api.auth_headers("tok123") == {"Authorization": "Bearer tok123"}


def test_empty_id_row_produces_no_doc():
    from gst_aar_law_shim import harvest_cbic_api as api

    page = [{"actName": "Nameless Id Act, 2017", "issueDt": "12-Apr-2017"}]
    assert api.normalize_acts(page) == []


def test_non_dict_payload_returns_empty(monkeypatch):
    from gst_aar_law_shim import harvest_cbic_api as api

    monkeypatch.setattr(api, "_req", lambda *a, **k: b"42")
    assert api.fetch_paged(api.BASE, "tok", "/api/cbic-act-msts") == []
    monkeypatch.setattr(api, "_req", lambda *a, **k: b'"just a string"')
    assert api.fetch_paged(api.BASE, "tok", "/api/cbic-act-msts") == []


def test_parse_listing_extracts_pdf_links():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    html = ('<a href="pdf/NN-26-2024_Eng.pdf">26/2024-CT</a>'
            '<a href="/about">skip</a>')
    rows = flat.parse_listing(html, "https://cbic-gst.gov.in/central-tax-notifications.html")
    assert rows[0]["pdf_url"] == "https://cbic-gst.gov.in/pdf/NN-26-2024_Eng.pdf"


def test_parse_notification_filename():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    assert flat.parse_notification_filename("NN-26-2024_Eng.pdf") == {
        "number": "26/2024", "category": "CT", "year": "2024"}


def test_lang_hint():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    assert flat.lang_hint("03-2022-CT-Hin.pdf") == "hi"
    assert flat.lang_hint("NN-26-2024_Eng.pdf") == "en"
    assert flat.lang_hint("circular-239.pdf") == ""


def test_hindi_listings_configured():
    from gst_aar_law_shim import harvest_cbic_flat as flat

    urls = [u for _, u in flat.LISTINGS]
    assert "https://cbic-gst.gov.in/hindi/central-tax-notifications.html" in urls
    assert "https://cbic-gst.gov.in/hindi/circulars.html" in urls
