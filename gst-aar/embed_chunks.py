#!/usr/bin/env python3
"""Embed all extracted ruling texts via LM Studio (nomic-embed-text-v1.5, 768-d)
and store them in data/aar.db for local semantic search.

Schema: chunks(chunk_id INTEGER PK, ruling_id, chunk_index, text, n_chars, embedding BLOB)
Resumable: skips (ruling_id, chunk_index) pairs already embedded.
Run: python3 embed_chunks.py            (incremental)
     python3 embed_chunks.py --limit 3 (smoke test)
"""
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "data" / "aar.db"
LMSTUDIO = "http://localhost:1234/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"

CHUNK_CHARS = 1600
CHUNK_OVERLAP = 200
BATCH = 32

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruling_id INTEGER NOT NULL REFERENCES rulings(id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    n_chars INTEGER,
    embedding BLOB,
    UNIQUE(ruling_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_ruling ON chunks(ruling_id);
"""


def chunk_text(text: str):
    """Split at paragraph boundaries into ~CHUNK_CHARS windows with overlap."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 > CHUNK_CHARS and cur:
            chunks.append(cur)
            cur = cur[-CHUNK_OVERLAP:] if CHUNK_OVERLAP else ""
        cur += ("\n\n" if cur else "") + p
    if cur.strip():
        chunks.append(cur)
    # drop tiny fragments
    return [c for c in chunks if len(c) > 80]


def embed_batch(texts):
    req = urllib.request.Request(
        LMSTUDIO,
        data=json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return [item["embedding"] for item in sorted(d["data"], key=lambda x: x["index"])]


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    rows = con.execute(
        "SELECT id, txt_file FROM rulings WHERE txt_file IS NOT NULL ORDER BY id"
    ).fetchall()
    if limit:
        rows = rows[:limit]
    print(f"{len(rows)} rulings with text")

    done = 0
    t0 = time.time()
    for ruling_id, txt_file in rows:
        path = ROOT / txt_file
        if not path.exists():
            continue
        full = path.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_text(full)
        already = {
            r[0] for r in con.execute(
                "SELECT chunk_index FROM chunks WHERE ruling_id=?", (ruling_id,)
            )
        }
        todo = [(i, c) for i, c in enumerate(chunks) if i not in already]
        if not todo:
            continue
        for start in range(0, len(todo), BATCH):
            batch = todo[start:start + BATCH]
            vecs = embed_batch([c for _, c in batch])
            con.executemany(
                "INSERT OR REPLACE INTO chunks (ruling_id, chunk_index, text, n_chars, embedding)"
                " VALUES (?,?,?,?,?)",
                [
                    (ruling_id, i, c, len(c),
                     sqlite3.Binary(__import__("struct").pack(f"{len(v)}f", *v)))
                    for (i, c), v in zip(batch, vecs)
                ],
            )
            con.commit()
        done += 1
        if done % 25 == 0:
            n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            rate = done / (time.time() - t0)
            print(f"[{done}/{len(rows)}] chunks so far: {n} ({rate:.1f} rulings/s)", flush=True)

    n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"DONE: {done} rulings newly embedded, {n} total chunks in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
