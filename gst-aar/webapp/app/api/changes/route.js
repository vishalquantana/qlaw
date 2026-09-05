import fs from "fs";
import path from "path";

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const since = searchParams.get("since") || "0000-00-00";
  const p = path.join(process.cwd(), "..", "data", "law", "changes.jsonl");
  if (!fs.existsSync(p)) return Response.json({ changes: [] });
  const changes = fs.readFileSync(p, "utf8").split("\n").filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch { return null; } })
    .filter((r) => r && (r.date || "") >= since);
  return Response.json({ changes });
}
