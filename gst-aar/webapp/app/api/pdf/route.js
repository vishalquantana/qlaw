import fs from "fs";
import path from "path";
import Database from "better-sqlite3";

// Streams a LOCAL corpus PDF inline (never redirects to publisher sites).
// GET /api/pdf?scope=aar|law&id=<rowid>
const DATA_ROOT = path.join(process.cwd(), "..", "data");

function resolveLocal(p) {
  if (!p) return null;
  const abs = path.isAbsolute(p) ? p : path.join(process.cwd(), "..", "..", p);
  const norm = path.normalize(abs);
  if (!norm.startsWith(DATA_ROOT + path.sep)) return null; // sandbox: data/ only
  return norm;
}

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const scope = searchParams.get("scope") || "aar";
  const id = parseInt(searchParams.get("id") || "", 10);
  if (!Number.isFinite(id)) return Response.json({ error: "bad id" }, { status: 400 });
  try {
    let local = null;
    if (scope === "law") {
      const db = new Database(path.join(DATA_ROOT, "law", "law.db"), { readonly: true });
      try {
        const row = db.prepare("SELECT local_path FROM documents WHERE id = ?").get(id);
        local = resolveLocal(row?.local_path);
      } finally { db.close(); }
    } else {
      const db = new Database(path.join(DATA_ROOT, "aar.db"), { readonly: true });
      try {
        const row = db.prepare("SELECT pdf_file FROM rulings WHERE id = ?").get(id);
        local = resolveLocal(row?.pdf_file);
      } finally { db.close(); }
    }
    if (!local || !fs.existsSync(local)) {
      return Response.json({ error: "local PDF not on file" }, { status: 404 });
    }
    const buf = fs.readFileSync(local);
    return new Response(buf, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `inline; filename="${path.basename(local)}"`,
        "Cache-Control": "private, max-age=3600",
      },
    });
  } catch (e) {
    return Response.json({ error: String((e && e.message) || e) }, { status: 500 });
  }
}
