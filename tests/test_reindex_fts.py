"""Pins for the FTS re-sync repair (offline, in-memory)."""
from __future__ import annotations

import sqlite3

from gst_aar_law_shim import law_db, reindex_fts


def _db():
    con = sqlite3.connect(":memory:")
    law_db.init_schema(con)
    return con


def _add(con, url: str, body: str) -> int:
    return law_db.upsert_document(con, {
        "source_url": url, "kind": "notification", "title": "T", "number": "1",
        "pub_date": "", "local_path": "", "sha256": "a" * 64, "body": body})


class TestDriftDetection:
    def test_upsert_alone_leaves_no_drift(self) -> None:
        con = _db()
        _add(con, "https://x.gov.in/a.pdf", "levy and collection")
        assert reindex_fts.drift(con) == (1, 0)

    def test_bare_update_creates_drift(self) -> None:
        # This is the bug the repair exists for: writing documents.body without
        # touching documents_fts leaves the text stored but unsearchable.
        con = _db()
        doc_id = _add(con, "https://x.gov.in/a.pdf", "")
        con.execute("UPDATE documents SET body=? WHERE id=?", ("real text here", doc_id))
        con.commit()
        assert reindex_fts.drift(con) == (1, 1)


class TestReindex:
    def test_reindex_repairs_drift(self) -> None:
        con = _db()
        doc_id = _add(con, "https://x.gov.in/a.pdf", "")
        con.execute("UPDATE documents SET body=? WHERE id=?", ("searchable levy text", doc_id))
        con.commit()
        reindex_fts.reindex(con)
        assert reindex_fts.drift(con) == (1, 0)

    def test_repaired_text_is_matchable(self) -> None:
        con = _db()
        doc_id = _add(con, "https://x.gov.in/a.pdf", "")
        con.execute("UPDATE documents SET body=? WHERE id=?", ("reverse charge mechanism", doc_id))
        con.commit()
        reindex_fts.reindex(con)
        n = con.execute("SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH ?",
                        ('"reverse"',)).fetchone()[0]
        assert n == 1

    def test_reindex_is_idempotent(self) -> None:
        con = _db()
        _add(con, "https://x.gov.in/a.pdf", "levy")
        reindex_fts.reindex(con)
        first = con.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
        reindex_fts.reindex(con)
        assert con.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0] == first
