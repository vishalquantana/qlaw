"""Pins for the State-Act harvester helpers and the stale-chunk detector."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import harvest_indiacode_states as st
from gst_aar_law_shim import law_db, rechunk_stale


class TestGstTitleFilter:
    def test_matches_the_state_act_titles(self) -> None:
        for t in ("THE GOA GOODS AND SERVICES TAX ACT, 2017",
                  "Tripura State Goods and Services Tax Act, 2017",
                  "THE JAMMU AND KASHMIR GOODS AND SERVICES TAX ACT, 2017",
                  "Tamil Nadu Goods and Services Tax Act,2017",
                  "Central Goods & Services Tax Act, 2017"):
            assert st.GST_RE.search(t), t

    def test_does_not_match_unrelated_tax_acts(self) -> None:
        for t in ("The Goa Value Added Tax Act, 2005",
                  "The Goa Motor Vehicles Tax Act, 1974",
                  "The Customs Act, 1962",
                  "The Goa Tax on Entry of Goods Act, 2000"):
            assert not st.GST_RE.search(t), t


class TestClean:
    def test_strips_tags_and_entities(self) -> None:
        out = st.clean("<p>Levy &amp; collection</p><br/>of tax")
        assert "<" not in out and ">" not in out
        assert "Levy & collection" in out

    def test_collapses_whitespace_but_keeps_paragraphs(self) -> None:
        out = st.clean("a   b\n\n\n\nc")
        assert "a b" in out
        assert "\n\n\n" not in out


class TestNotificationContentFilter:
    """A state's Notification collection is general gazette material, so the
    filter has to work on the text, not the title."""

    def test_state_gst_notification_text_is_kept(self) -> None:
        for t in ("Notification of HSN code under Tripura State Goods and Services Tax",
                  "Seeks to notify certain services under SGST",
                  "Notification No. 70/2018-State Tax, no. J. 21011/2/2018",
                  "Rate of CGST on specified goods"):
            assert st.GST_CONTENT_RE.search(t), t

    def test_unrelated_state_notifications_are_rejected(self) -> None:
        # real titles from Madhya Pradesh's collection
        for t in ("Madhya Pradesh Electricity Act, 2003, under authority of the"
                  " appointment of the Chairman",
                  "Re-constitution of Selection Committee for selection of Member (Law)",
                  "Collector appointed Administrators of fund of Zila Panchayats"):
            assert not st.GST_CONTENT_RE.search(t), t

    def test_a_title_without_gst_but_gst_body_is_kept(self) -> None:
        # "Notification 52 S.O. No. 52- 77 - TAX.pdf" carries no GST in the title
        title = "Notification 52 S.O. No. 52- 77 - TAX.pdf"
        body = "In exercise of the powers conferred by section 128 of the SGST Act..."
        assert not st.GST_RE.search(title)
        assert st.GST_CONTENT_RE.search(body)


def _db_with_doc(body: str, chunks: list[str]):
    con = sqlite3.connect(":memory:")
    law_db.init_schema(con)
    con.executescript("""CREATE TABLE IF NOT EXISTS law_chunks (
        chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL, chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL, n_chars INTEGER, embedding BLOB,
        UNIQUE(doc_id, chunk_index));""")
    doc_id = law_db.upsert_document(con, {
        "source_url": "https://x.gov.in/a.pdf", "kind": "t", "title": "T",
        "number": "", "pub_date": "", "local_path": "", "sha256": "a" * 64,
        "body": body})
    for i, c in enumerate(chunks):
        con.execute("INSERT INTO law_chunks (doc_id, chunk_index, text, n_chars)"
                    " VALUES (?,?,?,?)", (doc_id, i, c, len(c)))
    con.commit()
    return con


class TestStaleChunkDetection:
    def test_full_coverage_is_not_stale(self) -> None:
        con = _db_with_doc("x" * 1000, ["x" * 600, "x" * 400])
        assert rechunk_stale.stale_docs(con, 0.5) == []

    def test_truncated_chunks_are_stale(self) -> None:
        # the real failure: a 2,000-char body left with a 100-char chunk
        con = _db_with_doc("x" * 2000, ["x" * 100])
        assert len(rechunk_stale.stale_docs(con, 0.5)) == 1

    def test_exactly_half_is_not_stale(self) -> None:
        con = _db_with_doc("x" * 1000, ["x" * 500])
        assert rechunk_stale.stale_docs(con, 0.5) == []

    def test_ratio_is_configurable(self) -> None:
        con = _db_with_doc("x" * 1000, ["x" * 700])
        assert rechunk_stale.stale_docs(con, 0.5) == []
        assert len(rechunk_stale.stale_docs(con, 0.9)) == 1

    def test_document_without_chunks_is_not_reported(self) -> None:
        con = _db_with_doc("x" * 1000, [])
        assert rechunk_stale.stale_docs(con, 0.5) == []
