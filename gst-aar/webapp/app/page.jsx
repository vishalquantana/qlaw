"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const LS_KEY = "gst-chat-conversations-v1";

function loadConversations() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export default function Home() {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [hasText, setHasText] = useState(false);
  const [mode, setMode] = useState("keyword"); // keyword | semantic
  const [view, setView] = useState("chat"); // chat (hero) | browse
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chat, setChat] = useState([]); // [{role, content, sources?, error?}]
  const [previewId, setPreviewId] = useState(null); // selected source n for the rail preview
  const chatEndRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [offset, setOffset] = useState(0);
  const firstLoad = useRef(true);
  const chatRef = useRef(chat);
  chatRef.current = chat;
  const activeRef = useRef(activeId);
  activeRef.current = activeId;

  // persist active conversation on every change
  useEffect(() => {
    if (chat.length === 0) return;
    setConversations((prev) => {
      const id = activeRef.current || `c-${Date.now()}`;
      if (!activeRef.current) setActiveId(id);
      const title = chat.find((m) => m.role === "user")?.content.slice(0, 60) || "New chat";
      const next = [{ id, title, updatedAt: Date.now(), messages: chat },
        ...prev.filter((c) => c.id !== id)].slice(0, 50);
      try { localStorage.setItem(LS_KEY, JSON.stringify(next)); } catch { /* full — skip */ }
      return next;
    });
  }, [chat]);

  const openConversation = (id) => {
    const c = conversations.find((x) => x.id === id);
    if (!c) return;
    setActiveId(id);
    setChat(c.messages);
    setView("chat");
  };

  const newChat = () => {
    setActiveId(null);
    setChat([]);
    setView("chat");
  };

  const deleteConversation = (id) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      try { localStorage.setItem(LS_KEY, JSON.stringify(next)); } catch { /* skip */ }
      return next;
    });
    if (activeRef.current === id) {
      setActiveId(null);
      setChat([]);
    }
  };

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
    const history = [...chatRef.current, userMsg];
    setPreviewId(null);
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
  }, [chatBusy, chatInput]);

  useEffect(() => {
    if (firstLoad.current) {
      firstLoad.current = false;
      setConversations(loadConversations());
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

  // sources rail: latest assistant answer carrying sources
  const activeMsg = [...chat].reverse().find((m) => m.role === "assistant" && m.sources?.length);
  const activeSources = activeMsg?.sources || [];
  const selSource = activeSources.find((s) => s.n === previewId)
    || activeSources.find((s) => s.cited) || activeSources[0];

  return (
    <div className="shell">
      {/* ── sidebar ────────────────────────────── */}
      <aside className={`sidebar${sidebarOpen ? " open" : ""}`}>
        <button onClick={newChat} className="newchat">
          <span style={{ fontSize: 15 }}>＋</span> New chat
        </button>
        <div className="convlist">
          {conversations.length === 0 && (
            <p className="sidehint">Past conversations will appear here.</p>
          )}
          {conversations.map((c) => (
            <div key={c.id}
              onClick={() => openConversation(c.id)}
              className={`conv${c.id === activeId ? " active" : ""}`}>
              <span className="convtitle">{c.title}</span>
              <button
                onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }}
                className="convdel" aria-label="Delete conversation">✕</button>
            </div>
          ))}
        </div>
        <div className="sidefoot">
          <button onClick={() => setView(view === "chat" ? "browse" : "chat")} className="sidelink">
            {view === "chat" ? "⌕ Browse rulings" : "✦ Back to chat"}
          </button>
          {data?.stats && (
            <p className="sidestats">
              <span className="tabular">{data.stats.total.toLocaleString()}</span> rulings ·{" "}
              <span className="tabular">{data.stats.with_text.toLocaleString()}</span> full text
            </p>
          )}
        </div>
      </aside>
      {sidebarOpen && <div className="scrim" onClick={() => setSidebarOpen(false)} />}

      {/* ── main ───────────────────────────────── */}
      <div className="main">
        <header className="topbar">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="iconbtn" aria-label="Toggle sidebar">☰</button>
          <div className="brand">
            <div className="logo">§</div>
            <div>
              <div className="brandname">GST Legal Assistant</div>
              <div className="brandsub">rulings · statutes · Council minutes — grounded answers</div>
            </div>
          </div>
        </header>

        {view === "chat" ? (
          <div className="chatwrap">
            <div className="content3">
            <div className="chatcol">
            {chat.length === 0 ? (
              <div className="hero">
                <h1>Ask anything about GST law</h1>
                <p className="herosub">
                  grounded in retrieved rulings, statutes &amp; Council minutes · every claim cited to its official PDF
                </p>
                <div className="starters">
                  {[
                    "When was GSTR-3B due for Oct 2024 in Maharashtra?",
                    "Is late fee due if I file GSTR-9 but not GSTR-9C?",
                    "Can a s.83 attachment be renewed after a year?",
                    "Do summons u/s.70 bar parallel proceedings?",
                    "Why did the Council keep restaurant services at 5% without ITC?",
                    "What rate did the CEA propose as revenue-neutral?",
                  ].map((s, i) => (
                    <button key={s} onClick={() => sendChat(s)} className="starter" style={{ animationDelay: `${i * 70}ms` }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="thread">
                {chat.map((m, i) => (
                  <div key={i} className={`msgrow ${m.role}`}>
                    <div className={`bubble ${m.role}`}>
                      {m.pending && <span className="muted">retrieving rulings &amp; thinking…</span>}
                      {m.error && <span className="bad">Error: {m.error}</span>}
                      {!m.pending && !m.error && (
                        <div className="md"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            )}

            <div className="composer">
              {chat.length > 0 && (
                <button onClick={newChat} style={linkBtn} className="clearbtn">+ new chat</button>
              )}
              <div className="composerrow">
                <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Ask about rates, ITC, refunds, sections, cases…"
                  className="composerinput" />
                <button onClick={() => sendChat()} disabled={chatBusy || !chatInput.trim()} className="sendbtn">
                  {chatBusy ? "…" : "Send"}
                </button>
              </div>
              <p className="disclaimer">Grounded answers from official sources — always verify against the cited PDF. Not legal advice.</p>
            </div>
            </div>{/* chatcol */}
            {activeSources.length > 0 && (
            <aside className="sourcerail">
              <p className="railhead">Sources · from your local corpus</p>
              {activeSources.map((s) => (
                <button key={s.id} className={`srccard${selSource?.id === s.id ? " sel" : ""}`}
                  onMouseEnter={() => setPreviewId(s.n)} onClick={() => setPreviewId(s.n)} onFocus={() => setPreviewId(s.n)}>
                  <span className="srcctitle">{s.cited ? `[${s.n}] ` : ""}{s.applicant}</span>
                  <span className="srcmeta">{s.state} · {s.order_no} ({s.order_date})</span>
                </button>
              ))}
              {selSource && (
                <div className="pdfpane">
                  <p className="railhead">{selSource.cited ? `[${selSource.n}] ` : ""}{selSource.applicant}</p>
                  <iframe src={`${selSource.pdf_local}#page=${selSource.page || 1}`}
                    title={`PDF preview: ${selSource.applicant}`}
                    className="pdfview" sandbox="allow-same-origin" />
                  <p className="pagenote">
                    {selSource.page
                      ? `Opened at cited page ${selSource.page}.`
                      : "Page-level links coming — re-extraction with page markers is queued."}{" "}
                    <a href={selSource.pdf_url} target="_blank" rel="noreferrer" className="srclink">official source ↗</a>
                  </p>
                </div>
              )}
            </aside>
            )}
            </div>{/* content3 */}
          </div>
        ) : (
          <div className="browsewrap">
            <div className="card searchcard">
              <div className="searchrow">
                <div className="searchbox">
                  <span className="searchicon">⌕</span>
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && run(0)}
                    placeholder={mode === "semantic"
                      ? "Describe what you're looking for — meaning matters, not exact words…"
                      : "Search rulings — e.g. e-invoicing, HSN 9984, job work…"}
                    className="searchinput"
                  />
                </div>
                <button onClick={() => run(0)} disabled={loading} className="searchbtn">
                  {loading ? "Searching…" : "Search"}
                </button>
              </div>

              <div className="filters">
                <div className="modeseg">
                  {[["keyword", "Keyword"], ["semantic", "Semantic"]].map(([m, label]) => (
                    <button key={m} onClick={() => setMode(m)} className={`modesegbtn${mode === m ? " on" : ""}`}>
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
                    <span className="muted small">to</span>
                    <input type="date" value={to} onChange={(e) => setTo(e.target.value)} style={filterStyle} />
                    <label className="checklabel">
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
              </div>
            </div>

            {error && <p className="bad" style={{ marginTop: 14, fontSize: 13.5 }}>Error: {error}</p>}

            {data && (
              <>
                <p className="resultcount">
                  <strong className="tabular">{data.total.toLocaleString()}</strong> result{data.total === 1 ? "" : "s"}
                  {q ? (data.semantic ? " · ranked by semantic similarity" : " · ranked by relevance (BM25)") : " · newest first"}
                </p>

                <div className="results">
                  {data.rows.map((r) => (
                    <div key={r.id} onClick={() => openDoc(r.id)} className="result-card">
                      <div className="resulthead">
                        <strong className="resulttitle">{r.applicant}</strong>
                        <div className="resultmeta-right">
                          {data.semantic && r.sim != null && <Chip tone="accent">sim {r.sim.toFixed(3)}</Chip>}
                          <span className="muted small">{r.order_date || "date n/a"}</span>
                        </div>
                      </div>
                      <div className="resultmeta">
                        <span>{r.state}</span>·<span>{r.order_no || "order no. n/a"}</span>
                        {r.category && (<>·<span>{r.category}</span></>)}
                        <span className={`pill ${r.txt_file ? "good" : "warn"}`}>
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
                      <p className="snippet">
                        {(r.body_snippet && q ? r.body_snippet : r.brief || "").slice(0, 340).replaceAll("[[", "").replaceAll("]]", "")}
                        {(r.body_snippet || r.brief || "").length > 340 ? "…" : ""}
                      </p>
                      <a href={r.pdf_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="srclink">
                        official source ↗
                      </a>
                    </div>
                  ))}
                  {!data.rows.length && (
                    <div className="empty">
                      <div style={{ fontSize: 30, marginBottom: 8 }}>⌕</div>
                      no results — try broader terms or clear filters
                    </div>
                  )}
                </div>

                {data.total > 20 && (
                  <div className="pager">
                    <button disabled={offset === 0} onClick={() => run(Math.max(0, offset - 20))} style={pageBtn}>← Prev</button>
                    <span className="muted small tabular">
                      {offset + 1}–{Math.min(offset + 20, data.total)} of {data.total.toLocaleString()}
                    </span>
                    <button disabled={offset + 20 >= data.total} onClick={() => run(offset + 20)} style={pageBtn}>Next →</button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── document modal ─────────────────────── */}
      {selected && (
        <div onClick={() => setSelected(null)} className="modalback">
          <div onClick={(e) => e.stopPropagation()} className="modal">
            {selected.loading && <p className="muted">Loading…</p>}
            {selected.error && <p className="bad">{selected.error}</p>}
            {selected.doc && (
              <>
                <div className="modalhead">
                  <h2>{selected.doc.applicant}</h2>
                  <button onClick={() => setSelected(null)} style={closeBtn}>✕</button>
                </div>
                <p className="muted small" style={{ margin: "5px 0 0" }}>
                  {selected.doc.state} · {selected.doc.order_no} · {selected.doc.order_date} · {selected.doc.category}
                </p>
                <p className="modalbrief">{selected.doc.brief}</p>
                <p style={{ fontSize: 12, margin: "0 0 14px" }}>
                  <a href={selected.doc.pdf_url} target="_blank" rel="noreferrer" className="srclink strong">
                    official PDF ↗
                  </a>
                  <span className="muted">
                    {" "}· OCR: {selected.doc.extraction_status} · {selected.doc.pages || "?"} pages · {(selected.doc.chars || 0).toLocaleString()} chars
                  </span>
                </p>
                {selected.text ? (
                  <pre className="doctext">{selected.text}</pre>
                ) : (
                  <div className="notetext">
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
