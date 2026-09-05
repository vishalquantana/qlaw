import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "..", "data", "aar.db");
const LMSTUDIO = process.env.LMSTUDIO_URL || "http://localhost:1234/v1/embeddings";
const EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5";

let db, embCache = null, cacheKey = null;

function getDb() {
  if (!db) db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  return db;
}

function getEmbedding(text) {
  return fetch(LMSTUDIO, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: EMBED_MODEL, input: text }),
  }).then((r) => r.json());
}

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) || 1);
}

// Load all chunk vectors into memory once (10k-30k × 768 floats ≈ fine)
async function loadVectors() {
  const db = getDb();
  const { count } = db.prepare("SELECT COUNT(*) AS count FROM chunks").get();
  if (cacheKey === count && embCache) return embCache;
  const rows = db
    .prepare("SELECT chunk_id, ruling_id, text, embedding FROM chunks WHERE embedding IS NOT NULL")
    .all();
  const vecs = [];
  for (const r of rows) {
    const f32 = new Float32Array(r.embedding.buffer, r.embedding.byteOffset, r.embedding.length / 4);
    vecs.push({ chunk_id: r.chunk_id, ruling_id: r.ruling_id, text: r.text, vec: f32 });
  }
  embCache = vecs;
  cacheKey = count;
  return vecs;
}

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const q = (searchParams.get("q") || "").trim();
  const k = Math.min(parseInt(searchParams.get("limit") || "10", 10) || 10, 50);
  if (!q) return Response.json({ ok: false, error: "q required" }, { status: 400 });

  try {
    const vecs = await loadVectors();
    if (!vecs.length)
      return Response.json({ ok: true, total: 0, rows: [], note: "no embeddings yet" });

    const emb = await getEmbedding(q);
    const qv = new Float32Array(emb.data[0].embedding);

    const scored = vecs
      .map((v) => ({ ...v, score: cosine(qv, v.vec) }))
      .sort((a, b) => b.score - a.score)
      .slice(0, k);

    const db = getDb();
    const getRuling = db.prepare(
      `SELECT id, applicant, state, order_no, order_date, category, brief, pdf_url, txt_file
       FROM rulings WHERE id = ?`
    );
    const rows = scored.map((s) => ({
      score: Number(s.score.toFixed(4)),
      chunk_excerpt: s.text.slice(0, 400),
      ruling: getRuling.get(s.ruling_id) || null,
    }));
    return Response.json({ ok: true, total: vecs.length, rows });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
