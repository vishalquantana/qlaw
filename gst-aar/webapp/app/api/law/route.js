import Database from "better-sqlite3";
import path from "path";

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") || "";
  const kind = searchParams.get("kind") || "";
  let n = parseInt(searchParams.get("limit") || "10", 10);
  if (!Number.isFinite(n) || n <= 0) n = 10;
  const limit = Math.min(n, 50);
  if (!q) return Response.json({ results: [] });
  const dbPath = path.join(process.cwd(), "..", "data", "law", "law.db");
  const db = new Database(dbPath, { readonly: true });
  try {
    const terms = q.split(/\s+/).filter(Boolean).map((t) => `"${t.replace(/"/g, '""')}"`).join(" ");
    let rows = db.prepare(
      "SELECT d.id, d.title, d.number, d.kind, d.source_url, d.pub_date FROM documents d " +
      "JOIN documents_fts f ON f.rowid = d.id " +
      "JOIN (SELECT rowid, rank FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r " +
      "ON r.rowid = d.id ORDER BY r.rank, d.pub_date DESC LIMIT ?").all(terms, limit * 2);
    if (kind) rows = rows.filter((r) => r.kind === kind);
    return Response.json({ results: rows.slice(0, limit) });
  } catch (err) {
    return Response.json({ error: String((err && err.message) || err) }, { status: 400 });
  } finally {
    db.close();
  }
}
