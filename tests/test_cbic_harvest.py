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
