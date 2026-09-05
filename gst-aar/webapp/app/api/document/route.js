import Database from "better-sqlite3";
import path from "path";
import fs from "fs";

const ROOT = path.join(process.cwd(), "..");

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const id = parseInt(searchParams.get("id") || "", 10);
  if (!id) return Response.json({ ok: false, error: "id required" }, { status: 400 });

  try {
    const db = new Database(path.join(ROOT, "data", "aar.db"), { readonly: true });
    const doc = db
      .prepare(
        `SELECT id, sr_no, applicant, state, brief, order_no, order_date, category,
                pdf_url, pdf_file, txt_file, pages, chars, extraction_status
         FROM rulings WHERE id = ?`
      )
      .get(id);
    if (!doc) return Response.json({ ok: false, error: "not found" }, { status: 404 });

    let text = null;
    if (doc.txt_file && fs.existsSync(path.join(ROOT, doc.txt_file))) {
      text = fs.readFileSync(path.join(ROOT, doc.txt_file), "utf-8");
    }
    db.close();
    return Response.json({ ok: true, doc, text });
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
