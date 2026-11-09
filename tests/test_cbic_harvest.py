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


# --- full statute layer (acts / chapters / sections / rules / amendments) ---

ACT_NAMES = {"1000006": "Central Goods and Services Tax Act, 2017",
             "1000001": "Customs Act, 1962"}


def test_label_of_section_combines_number_and_heading():
    from gst_aar_law_shim import harvest_cbic_api as api

    rec = {"sectionNo": "Section 16",
           "sectionName": "Eligibility and conditions for taking input tax credit"}
    assert api.label_of("cbic_act_section", rec) == (
        "Section 16 — Eligibility and conditions for taking input tax credit")


def test_label_of_chapter():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert api.label_of("cbic_act_chapter",
                        {"chapterNo": "V", "chapterName": "Input Tax Credit"}) == (
        "Chapter V — Input Tax Credit")


def test_label_of_amendment_falls_back_to_filename():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert api.label_of("cbic_amendment",
                        {"htmlFileName": "CGST_Act_2017_30-March-2022.html"}) == (
        "CGST_Act_2017_30-March-2022.html")


def test_normalize_full_builds_searchable_body_with_act_name():
    from gst_aar_law_shim import harvest_cbic_api as api

    rows = [{"id": 999, "sectionNo": "Section 16",
             "sectionName": "Eligibility for input tax credit",
             "actId": {"id": 1000006}, "amendDt": "2022-09-28T05:30:00+05:30"}]
    docs = api.normalize_full("cbic-act-section-msts", rows, ACT_NAMES)
    assert len(docs) == 1
    d = docs[0]
    assert d["kind"] == "cbic_act_section"
    assert d["number"] == "Section 16"
    assert d["pub_date"] == "2022-09-28"
    assert "Central Goods and Services Tax Act, 2017" in d["body"]
    assert "Eligibility for input tax credit" in d["body"]
    assert d["source_url"] == (
        "https://taxinformation.cbic.gov.in/api/cbic-act-section-msts/999")


def test_gst_act_is_not_flagged_non_gst():
    from gst_aar_law_shim import harvest_cbic_api as api

    rows = [{"id": 1, "sectionNo": "Section 1", "sectionName": "Short title",
             "actId": {"id": 1000006}}]
    assert api.normalize_full("cbic-act-section-msts", rows, ACT_NAMES)[0]["_non_gst"] is False


def test_customs_act_section_is_flagged_non_gst():
    from gst_aar_law_shim import harvest_cbic_api as api

    rows = [{"id": 2, "sectionNo": "Section 1", "sectionName": "Short title",
             "actId": {"id": 1000001}}]
    assert api.normalize_full("cbic-act-section-msts", rows, ACT_NAMES)[0]["_non_gst"] is True


def test_gst_act_regex_covers_the_gst_family():
    from gst_aar_law_shim import harvest_cbic_api as api

    for name in ("Central Goods and Services Tax Act, 2017",
                 "Integrated Goods And Services Tax Act, 2017",
                 "Union Territory Goods And Services Tax Act, 2017",
                 "Goods And Services Tax (Compensation To States) Act, 2017",
                 "Constitution (One Hundred And First Amendment) Act, 2016"):
        assert api.GST_ACT_RE.search(name), name
    for name in ("Customs Act, 1962", "Central Excise Act, 1944",
                 "Customs Tariff Act, 1975",
                 "Provisional Collection of Taxes Act, 1931"):
        assert not api.GST_ACT_RE.search(name), name


def test_normalize_full_skips_rows_without_id_or_label():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert api.normalize_full("cbic-act-section-msts", [{"sectionNo": "x"}], {}) == []
    assert api.normalize_full("cbic-act-section-msts", [{"id": 5}], {}) == []


def test_every_endpoint_maps_to_a_kind():
    from gst_aar_law_shim import harvest_cbic_api as api

    assert set(api.ENDPOINTS) == {
        "cbic-act-msts", "cbic-act-chapter-msts", "cbic-act-section-msts",
        "cbic-rule-msts", "cbic-rule-chapter-msts", "cbic-rule-section-msts",
        "cbic-amendment-doc-histories", "cbic-regulation-msts", "cbic-form-msts"}
