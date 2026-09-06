import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "..", "data", "aar.db");
const LAW_PATH = path.join(process.cwd(), "..", "data", "law", "law.db");
const BASE = process.env.LMSTUDIO_URL?.replace("/embeddings", "") || "http://localhost:1234/v1";
const EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5";
const LLM_MODEL = process.env.LLM_MODEL || "ornith-1.5-35b-a3b";

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) || 1);
}

function retrieve(db, query) {
  const vecs = db
    .prepare("SELECT chunk_id, ruling_id, text, embedding FROM chunks WHERE embedding IS NOT NULL")
    .all();
  if (!vecs.length) return { contexts: [], note: "no embeddings yet — corpus OCR still in progress" };

  // hybrid: vector top-12 + BM25 ruling boost, reciprocal rank fusion
  return { vecs, note: null };
}

export async function POST(req) {
  const { messages } = await req.json(); // [{role: 'user'|'assistant', content}]
  if (!Array.isArray(messages) || !messages.length)
    return Response.json({ ok: false, error: "messages required" }, { status: 400 });

  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (!lastUser) return Response.json({ ok: false, error: "no user message" }, { status: 400 });

  try {
    const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });

    // ── retrieval on the latest question ──────────────────
    const vecs = db
      .prepare("SELECT chunk_id, ruling_id, text, embedding FROM chunks WHERE embedding IS NOT NULL")
      .all();
    if (!vecs.length)
      return Response.json({ ok: false, error: "no embeddings yet — corpus OCR still in progress" }, { status: 503 });

    const embRes = await fetch(`${BASE}/embeddings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: EMBED_MODEL, input: lastUser.content }),
    }).then((r) => r.json());
    const qv = new Float32Array(embRes.data[0].embedding);

    const vecRanked = vecs
      .map((v) => ({
        id: v.chunk_id,
        ruling_id: v.ruling_id,
        text: v.text,
        vs: cosine(qv, new Float32Array(v.embedding.buffer, v.embedding.byteOffset, v.embedding.length / 4)),
      }))
      .sort((a, b) => b.vs - a.vs)
      .slice(0, 12);

    const byVec = new Map(vecRanked.map((v, i) => [v.id, i]));

    const ftsTerms = lastUser.content.replace(/"/g, "").split(/\s+/)
      .filter((t) => t.length > 2).map((t) => `"${t}"`).join(" ");
    const bm25ChunkIds = new Set();
    if (ftsTerms) {
      try {
        const bmRulings = db
          .prepare(
            `SELECT r.id FROM rulings_fts f JOIN rulings r ON r.id = f.rowid
             WHERE rulings_fts MATCH ? ORDER BY f.rank LIMIT 8`
          )
          .all(ftsTerms);
        if (bmRulings.length) {
          const ph = bmRulings.map(() => "?").join(",");
          for (const r of db
            .prepare(`SELECT chunk_id FROM chunks WHERE ruling_id IN (${ph}) AND embedding IS NOT NULL`)
            .all(...bmRulings.map((x) => x.id)))
            bm25ChunkIds.add(r.chunk_id);
        }
      } catch { /* non-fatal */ }
    }

    const allIds = new Set([...byVec.keys(), ...bm25ChunkIds]);
    const fused = [...allIds]
      .map((id) => ({
        id,
        score: (byVec.has(id) ? 1 / (60 + byVec.get(id) + 1) : 0) + (bm25ChunkIds.has(id) ? 1 / 60 : 0),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);

    const getChunk = db.prepare("SELECT ruling_id, text FROM chunks WHERE chunk_id = ?");
    const getRuling = db.prepare(
      `SELECT id, applicant, state, order_no, order_date, pdf_url, brief FROM rulings WHERE id = ?`
    );

    const contexts = [];
    const seenRulings = new Set();
    for (const f of fused) {
      const c = getChunk.get(f.id);
      if (!c) continue;
      const r = getRuling.get(c.ruling_id);
      if (!r) continue;
      const n = contexts.length + 1;
      contexts.push({ n, ruling: r, text: c.text.slice(0, 1100) });
      seenRulings.add(r.id);
    }

    // ── law corpus (statutes, notifications, judgments, minutes) ──
    // FTS over law.db, rank then newest-first; non-GST rows excluded.
    // Stopwords removed: quoted FTS terms are ANDed, so fillers ("was",
    // "for", "what"…) would sink every query to zero rows.
    const STOP = new Set(("a,an,are,as,at,be,by,can,could,did,do,does,for,from,how,into,is,it,its,may,might,must,not,of,on,or,shall,should,than,that,the,their,then,there,these,they,this,those,under,was,were,what,when,where,which,who,why,will,with,would").split(","));
    const lawTerms = lastUser.content.replace(/"/g, "").split(/\s+/)
      .filter((t) => t.length > 2 && !STOP.has(t.toLowerCase())).map((t) => `"${t}"`).join(" ");
    try {
      const ldb = new Database(LAW_PATH, { readonly: true });
      try {
        const terms = lawTerms;
        if (terms) {
          const getSubj = ldb.prepare(
            `SELECT label, description, outcome, effective_date FROM law_subjects
             WHERE doc_id = ? AND description != '' ORDER BY id LIMIT 1`);
          const rows = ldb.prepare(
            `SELECT d.id, d.title, d.number, d.kind, d.pub_date, d.source_url, d.body
             FROM documents d JOIN documents_fts f ON f.rowid = d.id
             JOIN (SELECT rowid, rank FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r
               ON r.rowid = d.id
             WHERE NOT EXISTS (SELECT 1 FROM law_tags t WHERE t.doc_id = d.id AND t.tag = 'non-GST')
             ORDER BY r.rank, d.pub_date DESC LIMIT 4`).all(terms);
          for (const d of rows) {
            const s = getSubj.get(d.id);
            const holding = s ? `${s.label}. ${s.description} ${s.outcome ? `Holding: ${s.outcome}` : ""}`.trim() : "";
            const n = contexts.length + 1;
            contexts.push({
              n,
              ruling: {
                id: `law-${d.id}`,
                applicant: d.title,
                state: d.kind.replace(/_/g, " "),
                order_no: d.number,
                order_date: d.pub_date,
                pdf_url: d.source_url,
                pdf_local: `/api/pdf?scope=law&id=${d.id}`,
                brief: (s?.description || "").slice(0, 200),
              },
              text: (holding + "\n" + (d.body || "").slice(0, 900)).slice(0, 1100),
            });
          }
        }
      } finally { ldb.close(); }
    } catch { /* law corpus optional — AAR answers still work */ }
    if (!contexts.length)
      return Response.json({ ok: false, error: "no retrievable context for this question" }, { status: 503 });

    // ── conversation + grounded prompt ────────────────────
    const contextBlock = contexts
      .map((c) => `[${c.n}] ${c.ruling.applicant} (${c.ruling.state}, ${c.ruling.order_no}, dated ${c.ruling.order_date}):\n${c.text}`)
      .join("\n\n---\n\n");

    const systemPrompt =
      "You are a GST research assistant for Indian law (statutes, notifications, rulings, case law). " +
      "Answer the user's question using ONLY the numbered extracts provided. " +
      "Prefer statute/notification extracts over rulings for what the law IS; use rulings and " +
      "Council minutes as supporting or intent evidence, and say which is which. " +
      "Cite extracts inline as [1], [2] etc. matching the extract numbers. " +
      "If the extracts don't fully answer the question, say what's missing. " +
      "Be concise and factual. Advance rulings bind only the applicant they were given to — mention this when relevant. " +
      "Never invent numbers, dates or citations.";

    const chatMessages = [{ role: "system", content: systemPrompt }];
    // include prior conversation (compact) for follow-ups
    for (const m of messages.slice(-6)) {
      chatMessages.push({ role: m.role, content: m.content.slice(0, 2000) });
    }
    chatMessages.push({
      role: "user",
      content: `Question: ${lastUser.content}\n\nRuling extracts:\n\n${contextBlock}`,
    });

    const answerRes = await (async () => {
      // ornith burns reasoning tokens before answering; low max_tokens or a
      // cold model yields empty content — allow budget + one retry.
      for (let attempt = 0; attempt < 2; attempt++) {
        const r = await fetch(`${BASE}/chat/completions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: LLM_MODEL,
            temperature: 0.2,
            max_tokens: 4000,
            messages: chatMessages,
          }),
        }).then((r) => r.json());
        if (r.choices?.[0]?.message?.content?.trim()) return r;
        await new Promise((res) => setTimeout(res, 4000));
      }
      return { choices: [] };
    })();

    const answer = answerRes.choices?.[0]?.message?.content;
    if (!answer) return Response.json({ ok: false, error: "LLM returned no answer", raw: answerRes?.error?.message || null }, { status: 502 });

    // sources: rulings actually cited in the answer text first, then the rest
    const citedNums = new Set([...answer.matchAll(/\[(\d+)\]/g)].map((m) => parseInt(m[1])));
    const sources = [];
    const seen = new Set();
    for (const c of contexts.sort((a, b) => (citedNums.has(a.n) === citedNums.has(b.n) ? 0 : citedNums.has(a.n) ? -1 : 1))) {
      if (seen.has(c.ruling.id)) continue;
      seen.add(c.ruling.id);
      sources.push({
        n: c.n,
        cited: citedNums.has(c.n),
        id: c.ruling.id,
        applicant: c.ruling.applicant,
        state: c.ruling.state,
        order_no: c.ruling.order_no,
        order_date: c.ruling.order_date,
        pdf_url: c.ruling.pdf_url,
        pdf_local: c.ruling.pdf_local || `/api/pdf?scope=aar&id=${c.ruling.id}`,
        page: null, // page-level trace pending re-extraction with page markers
        brief: (c.ruling.brief || "").slice(0, 200),
        excerpt: c.text.slice(0, 300),
      });
    }

    return Response.json({ ok: true, answer, sources });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
