"""Pin the incremental law store: dedup, provenance, FTS hyphen quoting."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import law_db


def _memdb():
    con = sqlite3.connect(":memory:")
    law_db.init_schema(con)
    return con


class TestUpsertDedup:
    def test_same_source_url_upserts_once(self) -> None:
        con = _memdb()
        doc = {"source_url": "https://taxinformation.cbic.gov.in/x/1",
               "kind": "act", "title": "CGST Act", "number": "",
               "pub_date": "2017-04-12", "local_path": "", "sha256": "a" * 64,
               "body": "levy and collection"}
        id1 = law_db.upsert_document(con, doc)
        id2 = law_db.upsert_document(con, {**doc, "body": "levy and collection"})
        assert id1 == id2
        assert con.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1

    def test_changed_hash_updates_body(self) -> None:
        con = _memdb()
        doc = {"source_url": "https://cbic-gst.gov.in/pdf/n1.pdf",
               "kind": "notification", "title": "N1", "number": "1/2017-CT",
               "pub_date": "2017-06-28", "local_path": "", "sha256": "b" * 64,
               "body": "old text"}
        law_db.upsert_document(con, doc)
        law_db.upsert_document(con, {**doc, "sha256": "c" * 64, "body": "new text"})
        row = con.execute("SELECT body FROM documents").fetchone()
        assert row[0] == "new text"


class TestProvenance:
    def test_missing_source_url_raises(self) -> None:
        con = _memdb()
        try:
            law_db.upsert_document(con, {"source_url": "", "kind": "act",
                "title": "t", "number": "", "pub_date": "", "local_path": "",
                "sha256": "d" * 64, "body": "b"})
        except ValueError as e:
            assert "source_url" in str(e)
        else:
            raise AssertionError("expected ValueError")

    def test_non_gov_in_source_url_raises(self) -> None:
        con = _memdb()
        try:
            law_db.upsert_document(con, {"source_url": "https://example.com/x.pdf",
                "kind": "act", "title": "t", "number": "", "pub_date": "",
                "local_path": "", "sha256": "e" * 64, "body": "b"})
        except ValueError as e:
            assert ".gov.in" in str(e)
        else:
            raise AssertionError("expected ValueError")


class TestSearchQuoting:
    def test_hyphen_term_searches(self) -> None:
        con = _memdb()
        law_db.upsert_document(con, {"source_url": "https://cbic-gst.gov.in/pdf/e.pdf",
            "kind": "circular", "title": "e-invoicing", "number": "",
            "pub_date": "", "local_path": "", "sha256": "f" * 64,
            "body": "e-invoicing QR code B2C"})
        rows = law_db.search(con, "e-invoicing", 10)
        assert len(rows) == 1
