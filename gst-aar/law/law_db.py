"""Incremental SQLite store for the GST law corpus.

Upsert key: source_url. A changed sha256 updates body+metadata in place.
Every row requires a .gov.in source_url (spec §2).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    source_url TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    title TEXT DEFAULT '',
    number TEXT DEFAULT '',
    pub_date TEXT DEFAULT '',
    local_path TEXT DEFAULT '',
    sha256 TEXT DEFAULT '',
    body TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_documents_kind ON documents(kind);
CREATE INDEX IF NOT EXISTS idx_documents_number ON documents(number);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, number, body, tokenize='porter unicode61');
"""

LAW_DB = Path(__file__).parent.parent / "data" / "law" / "law.db"


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def init_db(path: Path = LAW_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    init_schema(con)
    return con


def _check_provenance(source_url: str) -> None:
    if not source_url:
        raise ValueError("source_url is required (no source URL, no processing)")
    if ".gov.in" not in source_url:
        raise ValueError(f"non-.gov.in source_url refused: {source_url}")


def upsert_document(con: sqlite3.Connection, doc: dict) -> int:
    _check_provenance(doc.get("source_url", ""))
    cur = con.execute(
        "INSERT INTO documents (source_url, kind, title, number, pub_date,"
        " local_path, sha256, body) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(source_url) DO UPDATE SET kind=excluded.kind,"
        " title=excluded.title, number=excluded.number, pub_date=excluded.pub_date,"
        " local_path=excluded.local_path, sha256=excluded.sha256, body=excluded.body",
        (doc["source_url"], doc.get("kind", ""), doc.get("title", ""),
         doc.get("number", ""), doc.get("pub_date", ""), doc.get("local_path", ""),
         doc.get("sha256", ""), doc.get("body", "")),
    )
    doc_id = cur.lastrowid or con.execute(
        "SELECT id FROM documents WHERE source_url=?", (doc["source_url"],)).fetchone()[0]
    con.execute("INSERT OR REPLACE INTO documents_fts(rowid, title, number, body)"
                " VALUES (?,?,?,?)",
                (doc_id, doc.get("title", ""), doc.get("number", ""), doc.get("body", "")))
    con.commit()
    return doc_id


def _quote_query(query: str) -> str:
    return " ".join(f'"{t}"' for t in query.split() if t)


def search(con: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return con.execute(
        "SELECT d.* FROM documents d JOIN documents_fts f ON f.rowid = d.id"
        " JOIN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r"
        " ON r.rowid = d.id LIMIT ?", (_quote_query(query), limit)).fetchall()
