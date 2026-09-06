#!/usr/bin/env python3
"""Embed law.db document bodies via LM Studio (nomic-embed-text-v1.5, 768-d).

Mirrors gst-aar/embed_chunks.py: paragraph-window chunking, batches of 32,
struct-packed float BLOBs (same format, so cosine code is reusable).
Stores in law_chunks(doc_id, chunk_index, ...) with UNIQUE(doc_id,
chunk_index) for resumability. Backfill-safe: re-run any time; changed
bodies need their stale chunks deleted first (manual DELETE, no auto-wipe).

Run: python3 embed_law.py --limit 2   (smoke test)
     python3 embed_law.py              (incremental full run)
"""
from __future__ import annotations

import importlib.util
import sqlite3
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
LAW_DB = ROOT.parent / "data" / "law" / "law.db"

BATCH = 32


def _load_sibling(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT.parent / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load sibling module {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_base = _load_sibling("aar_embed_chunks", "embed_chunks.py")
chunk_text = _base.chunk_text
embed_batch = _base.embed_batch
EMBED_MODEL = _base.EMBED_MODEL

SCHEMA = """
CREATE TABLE IF NOT EXISTS law_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    n_chars INTEGER,
    embedding BLOB,
    UNIQUE(doc_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_law_chunks_doc ON law_chunks(doc_id);
"""


def select_todo(chunks: list[str], already: set[int]) -> list[tuple[int, str]]:
    """Chunk (index, text) pairs not yet embedded."""
    return [(i, c) for i, c in enumerate(chunks) if i not in already]


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    con = sqlite3.connect(LAW_DB)
    try:
        con.executescript(SCHEMA)
        rows = con.execute(
            "SELECT id, body FROM documents WHERE body != '' ORDER BY id"
        ).fetchall()
        if limit:
            rows = rows[:limit]
        print(f"{len(rows)} law documents with body text")

        done, t0 = 0, time.time()
        for doc_id, body in rows:
            chunks = chunk_text(body)
            already = {
                r[0] for r in con.execute(
                    "SELECT chunk_index FROM law_chunks WHERE doc_id=?", (doc_id,)
                )
            }
            todo = select_todo(chunks, already)
            if not todo:
                continue
            for start in range(0, len(todo), BATCH):
                batch = todo[start:start + BATCH]
                vecs = embed_batch([c for _, c in batch])
                con.executemany(
                    "INSERT OR REPLACE INTO law_chunks"
                    " (doc_id, chunk_index, text, n_chars, embedding)"
                    " VALUES (?,?,?,?,?)",
                    [
                        (doc_id, i, c, len(c),
                         sqlite3.Binary(struct.pack(f"{len(v)}f", *v)))
                        for (i, c), v in zip(batch, vecs)
                    ],
                )
                con.commit()
            done += 1
        n = con.execute("SELECT COUNT(*) FROM law_chunks").fetchone()[0]
        print(f"DONE: {done} documents newly embedded,"
              f" {n} total law_chunks in {time.time()-t0:.0f}s")
    finally:
        con.close()


if __name__ == "__main__":
    main()
