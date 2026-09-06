"""Pin the law embedding pipeline: chunking + resume selection.

Offline tests only (no LM Studio). Live proof is the `--limit` + full run
against gst-aar/data/law/law.db.
"""
from __future__ import annotations

from gst_aar_law_shim import embed_law


class TestChunkText:
    def test_splits_at_paragraph_boundaries(self) -> None:
        paras = [f"para{i} " + "x" * 690 for i in range(3)]
        chunks = embed_law.chunk_text("\n\n".join(paras))
        assert len(chunks) == 2
        assert "para0" in chunks[0] and "para1" in chunks[0]
        assert "para2" in chunks[1]

    def test_drops_tiny_fragments(self) -> None:
        assert embed_law.chunk_text("only fifty-odd characters of text here.") == []


class TestSelectTodo:
    def test_skips_already_embedded(self) -> None:
        assert embed_law.select_todo(["a", "b", "c"], {0, 2}) == [(1, "b")]

    def test_empty_when_all_done(self) -> None:
        assert embed_law.select_todo(["a"], {0}) == []
