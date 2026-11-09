import Database from "better-sqlite3";
import path from "path";

// GET /api/rate?code=0401        -> rate lines for one HSN / SAC code
// GET /api/rate?q=milk           -> rate lines whose description matches
// GET /api/rate?code=9954&kind=service
//
// Backed by rate_facts / rate_codes, built from the CBIC rate schedule by
// gst-aar/law/harvest_gst_rates.py. Each line carries its own source_url, so a
// rate can always be traced back to the published schedule.
export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const code = (searchParams.get("code") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const kind = searchParams.get("kind") || "";
  let n = parseInt(searchParams.get("limit") || "20", 10);
  if (!Number.isFinite(n) || n <= 0) n = 20;
  const limit = Math.min(n, 100);
  if (!code && !q) return Response.json({ results: [] });

  const dbPath = path.join(process.cwd(), "..", "data", "law", "law.db");
  const db = new Database(dbPath, { readonly: true });
  try {
    const cols = "f.id, f.kind, f.schedule, f.sr_no, f.hsn_sac AS code, " +
      "f.description, f.cgst_rate, f.sgst_rate, f.igst_rate, f.cess, " +
      "f.condition, f.source_url";
    let rows;
    if (code) {
      rows = db.prepare(
        "SELECT " + cols + " FROM rate_codes c JOIN rate_facts f ON f.id = c.fact_id " +
        "WHERE c.code = ? ORDER BY f.kind, f.schedule, f.sr_no LIMIT ?").all(code, limit);
    } else {
      rows = db.prepare(
        "SELECT " + cols + " FROM rate_facts f WHERE f.description LIKE ? " +
        "ORDER BY f.kind, f.schedule, f.sr_no LIMIT ?").all("%" + q + "%", limit);
    }
    if (kind) rows = rows.filter((r) => r.kind === kind);
    return Response.json({ results: rows });
  } catch (err) {
    return Response.json({ error: String((err && err.message) || err) }, { status: 400 });
  } finally {
    db.close();
  }
}
