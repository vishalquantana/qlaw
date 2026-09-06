"""Pins for law ontology pass-1 and the status dashboard (offline)."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import law_db, law_ontology, status_dashboard


def _memdb():
    con = sqlite3.connect(":memory:")
    law_db.init_schema(con)
    con.executescript(law_ontology.SCHEMA)
    return con


class TestPass1:
    def test_extracts_hsn_notification_section(self) -> None:
        con = _memdb()
        doc_id = law_db.upsert_document(con, {
            "source_url": "https://cbic-gst.gov.in/pdf/t.pdf", "kind": "notification",
            "title": "t", "number": "11/2025-CT", "pub_date": "2025-01-22",
            "local_path": "", "sha256": "a" * 64,
            "body": "HSN 9984 services under section 16 of the CGST Act "
                    "vide Notification No. 11/2025-Central Tax dated 22-01-2025"})
        counts = law_ontology.pass1_doc(
            con, doc_id, "HSN 9984 services under section 16 of the CGST Act "
                         "vide Notification No. 11/2025-Central Tax dated 22-01-2025")
        assert counts["citations"] >= 3
        cites = {r[0] for r in con.execute(
            "SELECT cite_type FROM law_citations WHERE doc_id=?", (doc_id,))}
        assert {"hsn_sac", "notification", "section"} <= cites

    def test_idempotent(self) -> None:
        con = _memdb()
        doc_id = law_db.upsert_document(con, {
            "source_url": "https://cbic-gst.gov.in/pdf/u.pdf", "kind": "bill",
            "title": "u", "number": "", "pub_date": "", "local_path": "",
            "sha256": "b" * 64, "body": "HSN 5200 refund e-invoicing"})
        law_ontology.pass1_doc(con, doc_id, "HSN 5200 refund e-invoicing")
        law_ontology.pass1_doc(con, doc_id, "HSN 5200 refund e-invoicing")
        assert con.execute("SELECT COUNT(*) FROM law_citations").fetchone()[0] == 1


class TestDashboard:
    def test_build_contains_sections(self) -> None:
        html = status_dashboard.build()
        for section in ("Universe vs held", "Law documents by kind",
                        "AAR extraction funnel", "Ontology", "Embeddings"):
            assert section in html
