"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DARK = {
  bg: "#0f1117", card: "#171a23", card2: "#1d212e", border: "#2a2f3f",
  text: "#e8eaf0", muted: "#9aa1b5", accent: "#6c8cff", good: "#3ecf8e",
};

export default function Home() {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [hasText, setHasText] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [offset, setOffset] = useState(0);
  const firstLoad = useRef(true);

  const run = useCallback(
    async (off = 0) => {
      setLoading(true);
      setError(null);
      try {
        const p = new URLSearchParams();
        if (q) p.set("q", q);
        if (state) p.set("state", state);
        if (from) p.set("from", from);
        if (to) p.set("to", to);
        if (hasText) p.set("hasText", "1");
        p.set("offset", String(off));
        const res = await fetch(`/api/search?${p}`);
        const j = await res.json();
        if (!j.ok) throw new Error(j.error);
        setData(j);
        setOffset(off);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [q, state, from, to, hasText]
  );

  useEffect(() => {
    if (firstLoad.current) {
      firstLoad.current = false;
      run(0);
    }
  }, [run]);

  const openDoc = async (id) => {
    setSelected({ loading: true });
    const res = await fetch(`/api/document?id=${id}`);
    const j = await res.json();
    setSelected(j.ok ? j : { error: j.error });
  };

  const states = data?.states || [];

  return (
    <div style={{ background: DARK.bg, minHeight: "100vh", color: DARK.text, fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif", padding: "28px 20px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <h1 style={{ fontSize: 24, margin: 0, letterSpacing: "-0.4px" }}>GST AAR / AAAR Search</h1>
        <p style={{ color: DARK.muted, fontSize: 13.5, marginTop: 4 }}>
          {data?.stats
            ? `${data.stats.total.toLocaleString()} rulings indexed · ${data.stats.with_text.toLocaleString()} with full text · every result links to its official source`
            : "loading…"}
        </p>

        <div style={{ background: DARK.card, border: `1px solid ${DARK.border}`, borderRadius: 12, padding: 16, marginTop: 14 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run(0)}
              placeholder='Search rulings — e.g. "e-invoicing", "HSN 9984", "job work"…'
              style={{ flex: 1, background: DARK.card2, border: `1px solid ${DARK.border}`, borderRadius: 8, padding: "10px 14px", color: DARK.text, fontSize: 14.5, outline: "none" }}
            />
            <button onClick={() => run(0)} disabled={loading}
              style={{ background: DARK.accent, color: "#fff", border: "none", borderRadius: 8, padding: "10px 22px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
              {loading ? "…" : "Search"}
            </button>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
            <select value={state} onChange={(e) => { setState(e.target.value); }} style={filterStyle(DARK)}>
              <option value="">All states</option>
              {states.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} style={filterStyle(DARK)} />
            <span style={{ color: DARK.muted, fontSize: 12 }}>to</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} style={filterStyle(DARK)} />
            <label style={{ display: "flex", alignItems: "center", gap: 6, color: DARK.muted, fontSize: 12.5, cursor: "pointer" }}>
              <input type="checkbox" checked={hasText} onChange={(e) => setHasText(e.target.checked)} />
              full text only
            </label>
            {(q || state || from || to || hasText) && (
              <button onClick={() => { setQ(""); setState(""); setFrom(""); setTo(""); setHasText(false); }}
                style={{ background: "none", border: "none", color: DARK.muted, fontSize: 12.5, cursor: "pointer", textDecoration: "underline" }}>
                reset
              </button>
            )}
          </div>
        </div>

        {error && <p style={{ color: "#f56d6d", marginTop: 12 }}>Error: {error}</p>}

        {data && (
          <>
            <p style={{ color: DARK.muted, fontSize: 13, margin: "14px 0 8px" }}>
              {data.total.toLocaleString()} result{data.total === 1 ? "" : "s"}
              {q ? " · ranked by BM25 relevance" : " · newest first"}
            </p>
            <div style={{ display: "grid", gap: 10 }}>
              {data.rows.map((r) => (
                <div key={r.id} onClick={() => openDoc(r.id)}
                  style={{ background: DARK.card, border: `1px solid ${DARK.border}`, borderRadius: 10, padding: "13px 16px", cursor: "pointer" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                    <strong style={{ fontSize: 14.5 }}>{r.applicant}</strong>
                    <span style={{ color: DARK.muted, fontSize: 12 }}>{r.order_date || "date n/a"}</span>
                  </div>
                  <div style={{ color: DARK.muted, fontSize: 12.5, marginTop: 2 }}>
                    {r.state} · {r.order_no || "order no. n/a"} · {r.category || ""}
                    <span style={{
                      marginLeft: 8, padding: "1px 8px", borderRadius: 10, fontSize: 11,
                      background: r.txt_file ? "rgba(62,207,142,0.12)" : "rgba(245,183,89,0.12)",
                      color: r.txt_file ? DARK.good : "#f5b759",
                    }}>
                      {r.txt_file ? "full text" : "metadata only"}
                    </span>
                  </div>
                  <p style={{ color: DARK.muted, fontSize: 13, margin: "6px 0 0", lineHeight: 1.5 }}>
                    {(r.body_snippet && q ? r.body_snippet : r.brief || "").slice(0, 320)}
                    {(r.body_snippet || r.brief || "").length > 320 ? "…" : ""}
                  </p>
                  <a href={r.pdf_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                    style={{ color: DARK.accent, fontSize: 11.5, textDecoration: "none", wordBreak: "break-all" }}>
                    official source ↗
                  </a>
                </div>
              ))}
              {!data.rows.length && <p style={{ color: DARK.muted }}>no results — try broader terms or clear filters</p>}
            </div>

            {data.total > 20 && (
              <div style={{ display: "flex", gap: 10, justifyContent: "center", margin: "18px 0" }}>
                <button disabled={offset === 0} onClick={() => run(Math.max(0, offset - 20))} style={pageBtn(DARK)}>← prev</button>
                <span style={{ color: DARK.muted, fontSize: 13, alignSelf: "center" }}>
                  {offset + 1}–{Math.min(offset + 20, data.total)} of {data.total.toLocaleString()}
                </span>
                <button disabled={offset + 20 >= data.total} onClick={() => run(offset + 20)} style={pageBtn(DARK)}>next →</button>
              </div>
            )}
          </>
        )}
      </div>

      {selected && (
        <div onClick={() => setSelected(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "40px 16px", overflow: "auto" }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{ background: DARK.card, border: `1px solid ${DARK.border}`, borderRadius: 14, maxWidth: 780, width: "100%", padding: 24 }}>
            {selected.loading && <p style={{ color: DARK.muted }}>loading…</p>}
            {selected.error && <p style={{ color: "#f56d6d" }}>{selected.error}</p>}
            {selected.doc && (
              <>
                <h2 style={{ fontSize: 18, margin: "0 0 4px" }}>{selected.doc.applicant}</h2>
                <p style={{ color: DARK.muted, fontSize: 13 }}>
                  {selected.doc.state} · {selected.doc.order_no} · {selected.doc.order_date} · {selected.doc.category}
                </p>
                <p style={{ color: DARK.muted, fontSize: 13.5, margin: "10px 0" }}>{selected.doc.brief}</p>
                <p style={{ fontSize: 12, margin: "0 0 12px" }}>
                  <a href={selected.doc.pdf_url} target="_blank" rel="noreferrer" style={{ color: DARK.accent }}>official PDF ↗</a>
                  <span style={{ color: DARK.muted }}> · OCR: {selected.doc.extraction_status} · {selected.doc.pages || "?"} pages · {(selected.doc.chars || 0).toLocaleString()} chars</span>
                </p>
                {selected.text ? (
                  <pre style={{ background: DARK.card2, border: `1px solid ${DARK.border}`, borderRadius: 10, padding: 16, fontSize: 12, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: "55vh", overflow: "auto", color: DARK.text }}>
                    {selected.text}
                  </pre>
                ) : (
                  <p style={{ color: "#f5b759", fontSize: 13 }}>
                    Full text not yet extracted for this document (pending OCR run).
                  </p>
                )}
                <button onClick={() => setSelected(null)} style={{ ...pageBtn(DARK), marginTop: 14 }}>close</button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function filterStyle(DARK) {
  return {
    background: DARK.card2, border: `1px solid ${DARK.border}`, borderRadius: 8,
    padding: "7px 10px", color: DARK.text, fontSize: 13, outline: "none",
  };
}

function pageBtn(DARK) {
  return {
    background: DARK.card2, border: `1px solid ${DARK.border}`, borderRadius: 8,
    padding: "7px 16px", color: DARK.text, fontSize: 13, cursor: "pointer",
  };
}
