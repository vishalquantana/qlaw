"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export default function Home() {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [hasText, setHasText] = useState(false);
  const [mode, setMode] = useState("keyword"); // keyword | semantic
  const [askOpen, setAskOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chat, setChat] = useState([]); // [{role, content, sources?, error?}]
  const chatEndRef = useRef(null);
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
        if (mode === "semantic") {
          if (!q) throw new Error("enter a query");
          p.set("q", q);
          const res = await fetch(`/api/semantic?${p}`);
          const j = await res.json();
          if (!j.ok) throw new Error(j.error);
          setData({
            total: j.total, rows: j.rows.map((r) => ({
              id: r.ruling?.id, applicant: r.ruling?.applicant, state: r.ruling?.state,
              order_no: r.ruling?.order_no, order_date: r.ruling?.order_date,
              category: r.ruling?.category, brief: r.chunk_excerpt,
              pdf_url: r.ruling?.pdf_url, txt_file: r.ruling?.txt_file,
              sim: r.score,
            })), states: j.states || [], stats: null, semantic: true,
          });
          setOffset(0);
          return;
        }
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
    [q, state, from, to, hasText, mode]
  );

  const sendChat = useCallback(async (text) => {
    const content = (text ?? chatInput).trim();
    if (!content || chatBusy) return;
    const userMsg = { role: "user", content };
    const history = [...chat, userMsg];
    setChat([...history, { role: "assistant", content: "", pending: true }]);
    setChatInput("");
    setChatBusy(true);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      const j = await res.json();
      setChat((prev) => [
        ...prev.slice(0, -1),
        j.ok
          ? { role: "assistant", content: j.answer, sources: j.sources }
          : { role: "assistant", content: "", error: j.error },
      ]);
    } catch (e) {
      setChat((prev) => [...prev.slice(0, -1), { role: "assistant", content: "", error: String(e) }]);
    } finally {
      setChatBusy(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 80);
    }
  }, [chat, chatBusy, chatInput]);

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
    <div style={{ minHeight: "100vh", padding: "0 20px 60px" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>

        {/* ── header ─────────────────────────────── */}
        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "26px 0 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
              background: "linear-gradient(135deg, #4355d8, #7b8cf0)", color: "#fff", fontWeight: 800, fontSize: 16,
              boxShadow: "var(--shadow-md)", letterSpacing: -0.5,
            }}>§</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16.5, letterSpacing: -0.3 }}>GST AAR Search</div>
              <div style={{ color: "var(--muted)", fontSize: 12 }}>Indian advance rulings · rules-as-code</div>
            </div>
          </div>
          {data?.stats && (
            <div style={{ display: "flex", gap: 8 }}>
              <Chip>{data.stats.total.toLocaleString()} rulings</Chip>
              <Chip tone="good">{data.stats.with_text.toLocaleString()} full text</Chip>
            </div>
          )}
        </header>

        {/* ── search panel ───────────────────────── */}
        <div className="card" style={{
          background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16,
          padding: 18, marginTop: 22, boxShadow: "var(--shadow-md)",
        }}>
          <div style={{ display: "flex", gap: 10 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--muted)", fontSize: 15 }}>⌕</span>
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && run(0)}
                placeholder={mode === "semantic"
                  ? "Describe what you're looking for — meaning matters, not exact words…"
                  : "Search rulings — e.g. e-invoicing, HSN 9984, job work…"}
                style={{
                  width: "100%", background: "var(--card2)", border: "1px solid var(--border)", borderRadius: 10,
                  padding: "12px 14px 12px 38px", color: "var(--text)", fontSize: 15, outline: "none",
                  transition: "border-color .15s",
                }}
              />
            </div>
            <button onClick={() => run(0)} disabled={loading} style={{
              background: "var(--accent)", color: "#fff", border: "none", borderRadius: 10,
              padding: "0 26px", fontSize: 14.5, fontWeight: 600, cursor: "pointer", boxShadow: "var(--shadow-sm)",
            }}>
              {loading ? "Searching…" : "Search"}
            </button>
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
            {/* mode segmented control */}
            <div style={{
              display: "flex", background: "var(--card2)", border: "1px solid var(--border)",
              borderRadius: 9, padding: 3, gap: 2,
            }}>
              {[["keyword", "Keyword"], ["semantic", "Semantic"]].map(([m, label]) => (
                <button key={m} onClick={() => setMode(m)} style={{
                  background: mode === m ? "#fff" : "transparent",
                  color: mode === m ? "var(--accent)" : "var(--muted)",
                  border: mode === m ? "1px solid var(--border)" : "1px solid transparent",
                  borderRadius: 7, padding: "5px 13px", fontSize: 12.5, cursor: "pointer",
                  fontWeight: mode === m ? 600 : 500, boxShadow: mode === m ? "var(--shadow-sm)" : "none",
                }}>
                  {label}
                </button>
              ))}
            </div>

            {mode === "keyword" && (
              <>
                <select value={state} onChange={(e) => setState(e.target.value)} style={filterStyle}>
                  <option value="">All states</option>
                  {states.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} style={filterStyle} />
                <span style={{ color: "var(--muted)", fontSize: 12.5 }}>to</span>
                <input type="date" value={to} onChange={(e) => setTo(e.target.value)} style={filterStyle} />
                <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--muted)", fontSize: 13, cursor: "pointer", userSelect: "none" }}>
                  <input type="checkbox" checked={hasText} onChange={(e) => setHasText(e.target.checked)} />
                  full text only
                </label>
              </>
            )}

            {(q || state || from || to || hasText) && (
              <button onClick={() => { setQ(""); setState(""); setFrom(""); setTo(""); setHasText(false); }} style={linkBtn}>
                reset
              </button>
            )}

            <button onClick={() => setAskOpen(!askOpen)} style={{
              marginLeft: "auto", display: "flex", alignItems: "center", gap: 6,
              background: askOpen ? "var(--accent-soft)" : "#fff",
              border: `1px solid ${askOpen ? "var(--accent)" : "var(--border)"}`,
              borderRadius: 9, padding: "6px 14px", color: askOpen ? "var(--accent)" : "var(--text)",
              fontSize: 12.5, fontWeight: 600, cursor: "pointer",
            }}>
              ✦ Ask AI
            </button>
          </div>

          {askOpen && (
            <div style={{
              marginTop: 12, background: "#fff", border: "1px solid #d5daf6",
              borderRadius: 14, padding: 16, boxShadow: "var(--shadow-sm)",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span style={{ fontSize: 15 }}>✦</span>
                  <strong style={{ fontSize: 13.5 }}>Ask the corpus</strong>
                  <span style={{ color: "var(--muted)", fontSize: 11.5 }}>
                    grounded in retrieved rulings · every claim cited to its official PDF
                  </span>
                </div>
                {chat.length > 0 && (
                  <button onClick={() => setChat([])} style={linkBtn}>clear conversation</button>
                )}
              </div>

              {/* conversation thread */}
              {chat.length > 0 && (
                <div style={{ maxHeight: 420, overflowY: "auto", display: "grid", gap: 10, padding: "2px 2px 8px" }}>
                  {chat.map((m, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                      <div style={{
                        maxWidth: "88%", borderRadius: 14, padding: "11px 14px", fontSize: 13.5, lineHeight: 1.65,
                        whiteSpace: "pre-wrap",
                        ...(m.role === "user"
                          ? { background: "var(--accent)", color: "#fff", borderBottomRightRadius: 4 }
                          : { background: "var(--card2)", border: "1px solid var(--border)", color: "var(--text)", borderBottomLeftRadius: 4 }),
                      }}>
                        {m.pending && <span style={{ color: "var(--muted)" }}>retrieving rulings & thinking…</span>}
                        {m.error && <span style={{ color: "var(--bad)" }}>Error: {m.error}</span>}
                        {!m.pending && !m.error && m.content}

                        {!m.pending && m.sources?.length > 0 && (
                          <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
                            <p style={{ color: "var(--muted)", fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.6, margin: "0 0 6px" }}>
                              Grounded in
                            </p>
                            {m.sources.map((s) => (
                              <div key={s.id} style={{ marginBottom: 7, background: s.cited ? "var(--accent-soft)" : "transparent", border: s.cited ? "1px solid #d5daf6" : "1px solid transparent", borderRadius: 8, padding: s.cited ? "7px 10px" : "2px 10px" }}>
                                <a href={s.pdf_url} target="_blank" rel="noreferrer"
                                  style={{ fontSize: 12.5, color: "var(--accent)", fontWeight: s.cited ? 600 : 500, textDecoration: "none" }}>
                                  {s.cited ? `[${s.n}] ` : ""}{s.applicant} · {s.state} · {s.order_no} ({s.order_date}) ↗
                                </a>
                                <div style={{ color: "var(--muted)", fontSize: 11.5, marginTop: 2, lineHeight: 1.5 }}>
                                  {s.excerpt.slice(0, 180)}…
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              )}

              {/* suggested starters when empty */}
              {chat.length === 0 && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  {[
                    "What did rulings say about e-invoicing for education services?",
                    "GST rate for job work on handicraft goods?",
                    "Which rulings discuss ITC for ready mix concrete?",
                  ].map((s) => (
                    <button key={s} onClick={() => sendChat(s)} style={{
                      background: "var(--card2)", border: "1px solid var(--border)", borderRadius: 20,
                      padding: "6px 13px", fontSize: 12, color: "var(--muted)", cursor: "pointer",
                    }}>
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {/* input */}
              <div style={{ display: "flex", gap: 8 }}>
                <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Ask a question about the rulings…"
                  style={{ flex: 1, background: "var(--card2)", border: "1px solid var(--border)", borderRadius: 10, padding: "10px 13px", color: "var(--text)", fontSize: 14, outline: "none" }} />
                <button onClick={() => sendChat()} disabled={chatBusy || !chatInput.trim()} style={{
                  background: "var(--accent)", color: "#fff", border: "none", borderRadius: 10,
                  padding: "10px 20px", fontSize: 13.5, fontWeight: 600, cursor: "pointer", opacity: chatBusy || !chatInput.trim() ? 0.6 : 1,
                }}>
                  {chatBusy ? "…" : "Send"}
                </button>
              </div>
            </div>
          )}
        </div>

        {error && <p style={{ color: "var(--bad)", marginTop: 14, fontSize: 13.5 }}>Error: {error}</p>}

        {data && (
          <>
            <p style={{ color: "var(--muted)", fontSize: 13, margin: "18px 2px 10px" }}>
              <strong style={{ color: "var(--text)", fontWeight: 600 }}>{data.total.toLocaleString()}</strong> result{data.total === 1 ? "" : "s"}
              {q ? (data.semantic ? " · ranked by semantic similarity" : " · ranked by relevance (BM25)") : " · newest first"}
            </p>

            <div style={{ display: "grid", gap: 10 }}>
              {data.rows.map((r) => (
                <div key={r.id} onClick={() => openDoc(r.id)} className="result-card"
                  style={{
                    background: "var(--card)", border: "1px solid var(--border)", borderRadius: 13,
                    padding: "15px 18px", cursor: "pointer", transition: "box-shadow .15s, transform .15s, border-color .15s",
                  }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong style={{ fontSize: 15, letterSpacing: -0.2 }}>{r.applicant}</strong>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      {data.semantic && r.sim != null && <Chip tone="accent">sim {r.sim.toFixed(3)}</Chip>}
                      <span style={{ color: "var(--muted)", fontSize: 12.5 }}>{r.order_date || "date n/a"}</span>
                    </div>
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 3, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span>{r.state}</span>·<span>{r.order_no || "order no. n/a"}</span>
                    {r.category && (<>·<span>{r.category}</span></>)}
                    <span style={{
                      padding: "1.5px 9px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                      background: r.txt_file ? "var(--good-soft)" : "var(--warn-soft)",
                      color: r.txt_file ? "var(--good)" : "var(--warn)",
                    }}>
                      {r.txt_file ? "full text" : "metadata only"}
                    </span>
                    {r.ontology?.outcome && <OutcomeBadge outcome={r.ontology.outcome} />}
                    {r.ontology?.tags?.map((t) => <Chip key={t} tone="accent">{t}</Chip>)}
                    {r.ontology?.hsn && (
                      <Chip tone="default">
                        HSN {r.ontology.hsn}{r.ontology.rate_held ? ` · ${r.ontology.rate_held}` : ""}
                      </Chip>
                    )}
                  </div>
                  <p style={{ color: "#3f4654", fontSize: 13.5, margin: "8px 0 0", lineHeight: 1.6 }}>
                    {(r.body_snippet && q ? r.body_snippet : r.brief || "").slice(0, 340).replaceAll("[[", "").replaceAll("]]", "")}
                    {(r.body_snippet || r.brief || "").length > 340 ? "…" : ""}
                  </p>
                  <a href={r.pdf_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                    style={{ color: "var(--accent)", fontSize: 12, textDecoration: "none", fontWeight: 500, wordBreak: "break-all" }}>
                    official source ↗
                  </a>
                </div>
              ))}
              {!data.rows.length && (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--muted)" }}>
                  <div style={{ fontSize: 30, marginBottom: 8 }}>⌕</div>
                  no results — try broader terms or clear filters
                </div>
              )}
            </div>

            {data.total > 20 && (
              <div style={{ display: "flex", gap: 14, justifyContent: "center", margin: "22px 0", alignItems: "center" }}>
                <button disabled={offset === 0} onClick={() => run(Math.max(0, offset - 20))} style={pageBtn}>← Prev</button>
                <span style={{ color: "var(--muted)", fontSize: 13 }}>
                  {offset + 1}–{Math.min(offset + 20, data.total)} of {data.total.toLocaleString()}
                </span>
                <button disabled={offset + 20 >= data.total} onClick={() => run(offset + 20)} style={pageBtn}>Next →</button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── document modal ─────────────────────── */}
      {selected && (
        <div onClick={() => setSelected(null)}
          style={{
            position: "fixed", inset: 0, background: "rgba(22,24,29,0.45)", backdropFilter: "blur(3px)",
            display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "48px 16px", overflow: "auto", zIndex: 50,
          }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--card)", borderRadius: 18, maxWidth: 800, width: "100%",
              padding: 28, boxShadow: "var(--shadow-lg)",
            }}>
            {selected.loading && <p style={{ color: "var(--muted)" }}>Loading…</p>}
            {selected.error && <p style={{ color: "var(--bad)" }}>{selected.error}</p>}
            {selected.doc && (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <h2 style={{ fontSize: 19, margin: 0, letterSpacing: -0.3 }}>{selected.doc.applicant}</h2>
                  <button onClick={() => setSelected(null)} style={closeBtn}>✕</button>
                </div>
                <p style={{ color: "var(--muted)", fontSize: 13, margin: "5px 0 0" }}>
                  {selected.doc.state} · {selected.doc.order_no} · {selected.doc.order_date} · {selected.doc.category}
                </p>
                <p style={{ color: "#3f4654", fontSize: 13.5, margin: "12px 0", lineHeight: 1.6 }}>{selected.doc.brief}</p>
                <p style={{ fontSize: 12, margin: "0 0 14px" }}>
                  <a href={selected.doc.pdf_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>
                    official PDF ↗
                  </a>
                  <span style={{ color: "var(--muted)" }}>
                    {" "}· OCR: {selected.doc.extraction_status} · {selected.doc.pages || "?"} pages · {(selected.doc.chars || 0).toLocaleString()} chars
                  </span>
                </p>
                {selected.text ? (
                  <pre style={{
                    background: "var(--card2)", border: "1px solid var(--border)", borderRadius: 12, padding: 18,
                    fontSize: 12.5, lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word",
                    maxHeight: "55vh", overflow: "auto", color: "var(--text)",
                  }}>{selected.text}</pre>
                ) : (
                  <div style={{
                    background: "var(--warn-soft)", border: "1px solid #f3ddb8", borderRadius: 10,
                    padding: 14, color: "var(--warn)", fontSize: 13.5,
                  }}>
                    Full text not yet extracted for this document (OCR still processing the corpus).
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function OutcomeBadge({ outcome }) {
  const map = {
    ruling_given: { label: "✓ ruling given", bg: "var(--good-soft)", fg: "var(--good)" },
    withdrawn: { label: "withdrawn", bg: "var(--warn-soft)", fg: "var(--warn)" },
    rejected: { label: "rejected", bg: "#fdecea", fg: "var(--bad)" },
    no_ruling: { label: "no ruling", bg: "#f1f2f6", fg: "var(--muted)" },
    application_refused: { label: "refused", bg: "#fdecea", fg: "var(--bad)" },
  };
  const s = map[outcome] || { label: outcome, bg: "#f1f2f6", fg: "var(--muted)" };
  return (
    <span style={{ padding: "1.5px 9px", borderRadius: 20, fontSize: 11, fontWeight: 700, background: s.bg, color: s.fg }}>
      {s.label}
    </span>
  );
}

function Chip({ children, tone = "default" }) {
  const tones = {
    default: { background: "#fff", color: "var(--muted)", border: "1px solid var(--border)" },
    good: { background: "var(--good-soft)", color: "var(--good)", border: "1px solid #cdeadd" },
    accent: { background: "var(--accent-soft)", color: "var(--accent)", border: "1px solid #d5daf6" },
  };
  return (
    <span style={{ ...tones[tone], padding: "3px 11px", borderRadius: 20, fontSize: 11.5, fontWeight: 600, whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

const filterStyle = {
  background: "#fff", border: "1px solid var(--border)", borderRadius: 9,
  padding: "6px 11px", color: "var(--text)", fontSize: 13, outline: "none",
};

const linkBtn = {
  background: "none", border: "none", color: "var(--muted)", fontSize: 12.5,
  cursor: "pointer", textDecoration: "underline", padding: 0,
};

const pageBtn = {
  background: "#fff", border: "1px solid var(--border)", borderRadius: 9,
  padding: "8px 18px", color: "var(--text)", fontSize: 13, cursor: "pointer",
  fontWeight: 500, boxShadow: "var(--shadow-sm)",
};

const closeBtn = {
  background: "var(--card2)", border: "1px solid var(--border)", borderRadius: 8,
  width: 30, height: 30, cursor: "pointer", color: "var(--muted)", fontSize: 13, flexShrink: 0,
};
