import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "..", "data", "aar.db");

let db;
function getDb() {
  if (!db) {
    db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  }
  return db;
}

function ftsQuery(q) {
  // quote each term so hyphens etc. don't parse as FTS column syntax
  return q
    .replace(/"/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .map((t) => `"${t}"`)
    .join(" ");
}

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const q = (searchParams.get("q") || "").trim();
  const state = (searchParams.get("state") || "").trim();
  const dateFrom = (searchParams.get("from") || "").trim();
  const dateTo = (searchParams.get("to") || "").trim();
  const hasTextOnly = searchParams.get("hasText") === "1";
  const limit = Math.min(parseInt(searchParams.get("limit") || "20", 10) || 20, 100);
  const offset = Math.max(parseInt(searchParams.get("offset") || "0", 10) || 0, 0);

  try {
    const db = getDb();
    const where = [];
    const params = [];

    let from = "rulings r";
    if (q) {
      from = "rulings_fts f JOIN rulings r ON r.id = f.rowid";
      where.push("rulings_fts MATCH ?");
      params.push(ftsQuery(q));
    }
    if (state) {
      where.push("r.state LIKE ? COLLATE NOCASE");
      params.push(`%${state}%`);
    }
    if (dateFrom) {
      where.push("r.order_date >= ?");
      params.push(dateFrom);
    }
    if (dateTo) {
      where.push("r.order_date <= ?");
      params.push(dateTo);
    }
    if (hasTextOnly) {
      where.push("r.txt_file IS NOT NULL");
    }
    const whereSql = where.length ? "WHERE " + where.join(" AND ") : "";
    const orderSql = q ? "ORDER BY f.rank" : "ORDER BY r.order_date DESC, r.id DESC";

    const selectCols = q
      ? `r.id, r.sr_no, r.applicant, r.state, r.order_no, r.order_date, r.category,
         r.brief, r.pdf_url, r.txt_file, r.extraction_status, f.rank AS score,
         snippet(rulings_fts, 4, '[[', ']]', ' … ', 24) AS body_snippet`
      : `r.id, r.sr_no, r.applicant, r.state, r.order_no, r.order_date, r.category,
         r.brief, r.pdf_url, r.txt_file, r.extraction_status, NULL AS score,
         NULL AS body_snippet`;

    const total = db
      .prepare(`SELECT COUNT(*) AS n FROM ${from} ${whereSql}`)
      .get(...params).n;

    const rows = db
      .prepare(
        `SELECT ${selectCols} FROM ${from} ${whereSql} ${orderSql} LIMIT ? OFFSET ?`
      )
      .all(...params, limit, offset);

    const states = db
      .prepare("SELECT DISTINCT state FROM rulings ORDER BY state")
      .all()
      .map((s) => s.state)
      .filter(Boolean);

    const stats = db
      .prepare(
        `SELECT COUNT(*) AS total,
                SUM(CASE WHEN txt_file IS NOT NULL THEN 1 ELSE 0 END) AS with_text
         FROM rulings`
      )
      .get();

    return Response.json({ ok: true, total, rows, states, stats });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
