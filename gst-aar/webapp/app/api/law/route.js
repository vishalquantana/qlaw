import Database from "better-sqlite3";
import path from "path";

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") || "";
  const kind = searchParams.get("kind") || "";
  const limit = Math.min(parseInt(searchParams.get("limit") || "10", 10), 50);
  if (!q) return Response.json({ results: [] });
  const dbPath = path.join(process.cwd(), "..", "data", "law", "law.db");
  const db = new Database(dbPath, { readonly: true });
  const terms = q.split(/\s+/).filter(Boolean).map((t) => `"${t}"`).join(" ");
  let rows = db.prepare(
    "SELECT d.id, d.title, d.number, d.kind, d.source_url FROM documents d " +
    "JOIN documents_fts f ON f.rowid = d.id " +
    "JOIN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? LIMIT -1) r " +
    "ON r.rowid = d.id LIMIT ?").all(terms, limit * 2);
  if (kind) rows = rows.filter((r) => r.kind === kind);
  return Response.json({ results: rows.slice(0, limit) });
}
