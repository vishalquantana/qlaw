import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "..", "data", "aar.db");
const BASE = process.env.LMSTUDIO_URL?.replace("/embeddings", "") || "http://localhost:1234/v1";
const EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5";
const LLM_MODEL = process.env.LLM_MODEL || "ornith-1.5-35b-a3b";

export async function POST(req) {
  const { question } = await req.json();
  if (!question?.trim())
    return Response.json({ ok: false, error: "question required" }, { status: 400 });

  try {
    const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });

    // 1. hybrid retrieval: vector similarity + BM25 keyword, fused
    const vecs = db
      .prepare("SELECT chunk_id, ruling_id, text, embedding FROM chunks WHERE embedding IS NOT NULL")
      .all();
    if (!vecs.length)
      return Response.json({ ok: false, error: "no embeddings yet — still OCR-ing the corpus" }, { status: 503 });

    const embRes = await fetch(`${BASE}/embeddings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: EMBED_MODEL, input: question }),
    }).then((r) => r.json());
    const qv = new Float32Array(embRes.data[0].embedding);

    const cos = (a, b) => {
      let dot = 0, na = 0, nb = 0;
      for (let i = 0; i < a.length; i++) {
        dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i];
      }
      return dot / (Math.sqrt(na) * Math.sqrt(nb) || 1);
    };

    const byVec = new Map(
      vecs
        .map((v) => ({ id: v.chunk_id, vs: cos(qv, new Float32Array(v.embedding.buffer, v.embedding.byteOffset, v.embedding.length / 4)) }))
        .sort((a, b) => b.vs - a.vs)
        .slice(0, 12)
        .map((v) => [v.id, v.vs])
    );

    // BM25 on chunks is not indexed; keyword-filter rulings via FTS then boost their chunks
    const ftsTerms = question.replace(/"/g, "").split(/\s+/).filter((t) => t.length > 2)
      .map((t) => `"${t}"`).join(" ");
    let bm25ChunkIds = new Set();
    try {
      const bmRows = db
        .prepare(
          `SELECT r.id FROM rulings_fts f JOIN rulings r ON r.id = f.rowid
           WHERE rulings_fts MATCH ? ORDER BY f.rank LIMIT 8`
        )
        .all(ftsTerms);
      if (bmRows.length) {
        const ph = bmRows.map(() => "?").join(",");
        const ids = db
          .prepare(`SELECT chunk_id FROM chunks WHERE ruling_id IN (${ph}) AND embedding IS NOT NULL`)
          .all(...bmRows.map((r) => r.id));
        bm25ChunkIds = new Set(ids.map((r) => r.chunk_id));
      }
    } catch { /* fts parse issues are non-fatal */ }

    // reciprocal rank fusion
    const vecRank = [...byVec.keys()];
    const allIds = new Set([...vecRank, ...bm25ChunkIds]);
    const fused = [...allIds].map((id) => {
      const vi = vecRank.indexOf(id);
      const score = (vi >= 0 ? 1 / (60 + vi + 1) : 0) + (bm25ChunkIds.has(id) ? 1 / 60 : 0);
      return { id, score };
    }).sort((a, b) => b.score - a.score).slice(0, 8);

    const getChunk = db.prepare("SELECT ruling_id, text FROM chunks WHERE chunk_id = ?");
    const getRuling = db.prepare(
      `SELECT id, applicant, state, order_no, order_date, pdf_url FROM rulings WHERE id = ?`
    );

    const contexts = [];
    for (const f of fused) {
      const c = getChunk.get(f.id);
      if (!c) continue;
      const r = getRuling.get(c.ruling_id);
      if (!r) continue;
      contexts.push({ n: contexts.length + 1, ruling: r, text: c.text.slice(0, 1200) });
    }
    if (!contexts.length)
      return Response.json({ ok: false, error: "no retrievable context",
        diag: { vecs: vecs.length, byVec: byVec.size, bm25: bm25ChunkIds.size, fused: fused.length } }, { status: 503 });

    // 2. RAG prompt
    const contextBlock = contexts
      .map((c) => `[${c.n}] ${c.ruling.applicant} (${c.ruling.state}, ${c.ruling.order_no}, ${c.ruling.order_date}):\n${c.text}`)
      .join("\n\n---\n\n");

    const answerRes = await fetch(`${BASE}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: LLM_MODEL,
        temperature: 0.2,
        max_tokens: 1200,
        messages: [
          {
            role: "system",
            content:
              "You are a GST research assistant for Indian advance rulings (AAR/AAAR). " +
              "Answer ONLY from the provided ruling extracts. Cite rulings inline as [1], [2] matching the numbered sources. " +
              "If the extracts don't contain the answer, say so plainly. Do not give legal advice; note that rulings bind only the applicant.",
          },
          {
            role: "user",
            content: `Question: ${question}\n\nRuling extracts:\n\n${contextBlock}`,
          },
        ],
      }),
    }).then((r) => r.json());

    const answer = answerRes.choices?.[0]?.message?.content || "(no answer generated)";

    // dedupe cited rulings
    const cited = [];
    const seen = new Set();
    for (const c of contexts) {
      if (!seen.has(c.ruling.id)) {
        seen.add(c.ruling.id);
        cited.push(c.ruling);
      }
    }

    return Response.json({ ok: true, answer, sources: cited });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
