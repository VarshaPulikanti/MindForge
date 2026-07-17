import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import AuthPage from "./AuthPage";
import { api, getToken, setToken } from "./api";
import type { Analysis, ChatMessage, Document, Health, User } from "./types";
import "./App.css";

const CHAT_SUGGESTIONS = [
  "What is this about?",
  "Summarize",
  "Sentiment",
  "Keywords",
  "Key points",
  "Readability",
] as const;

const SELECTED_DOC_KEY = "mindforge:selectedId";

const SAMPLE_TEXT = `Artificial intelligence is transforming how we work, learn, and create. 
Modern language models can summarize documents, answer questions, and detect sentiment with remarkable accuracy.
This platform uses hybrid RAG retrieval and optional Groq LLM for chat answers.
Upload any article, notes, or essay — then analyze it and chat about the content.`;

function sentimentClass(s: string) {
  if (s === "positive") return "chip-positive";
  if (s === "negative") return "chip-negative";
  return "chip-neutral";
}

function scoreToPercent(score: number) {
  return Math.round(((score + 1) / 2) * 100);
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [health, setHealth] = useState<Health | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<Analysis[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [title, setTitle] = useState("My first document");
  const [content, setContent] = useState(SAMPLE_TEXT);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [docExpanded, setDocExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const selected = documents.find((d) => d.id === selectedId) ?? null;

  const loadDocuments = useCallback(async () => {
    const docs = await api.listDocuments();
    setDocuments(docs);
    return docs;
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    const token = getToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        return loadDocuments().then((docs) => {
          const raw = sessionStorage.getItem(SELECTED_DOC_KEY);
          if (!raw) return;
          const id = Number(raw);
          if (docs.some((d) => d.id === id)) {
            return selectDocument(id);
          }
          sessionStorage.removeItem(SELECTED_DOC_KEY);
        });
      })
      .catch(() => {
        setToken(null);
        setUser(null);
      })
      .finally(() => setAuthLoading(false));
  }, [loadDocuments]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const selectDocument = async (id: number) => {
    setSelectedId(id);
    sessionStorage.setItem(SELECTED_DOC_KEY, String(id));
    setDocExpanded(false);
    setError(null);
    try {
      const [analyses, msgs] = await Promise.all([
        api.listAnalyses(id),
        api.listMessages(id),
      ]);
      setAnalysisHistory(analyses);
      setAnalysis(analyses[0] ?? null);
      setMessages(msgs);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();
    if (!trimmedTitle) {
      setError("Please enter a title.");
      return;
    }
    if (trimmedContent.length < 10) {
      setError(`Document text must be at least 10 characters (currently ${trimmedContent.length}).`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const doc = await api.createDocument(trimmedTitle, trimmedContent);
      await loadDocuments();
      setSelectedId(doc.id);
      setAnalysis(null);
      setAnalysisHistory([]);
      setMessages([]);
      try {
        await selectDocument(doc.id);
      } catch {
        // Document saved; analyses/messages load is optional
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create document";
      if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
        setError("Cannot reach the API. Is the backend running on port 8000?");
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const doc = await api.uploadDocument(file, title || undefined);
      await loadDocuments();
      setSelectedId(doc.id);
      await selectDocument(doc.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleAnalyze = async () => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyze(selectedId);
      setAnalysis(result);
      const history = await api.listAnalyses(selectedId);
      setAnalysisHistory(history);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedId || !chatInput.trim()) return;
    setChatLoading(true);
    setError(null);
    const text = chatInput.trim();
    setChatInput("");
    try {
      const pair = await api.chat(selectedId, text);
      setMessages((prev) => [...prev, ...pair]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      setChatInput(text);
    } finally {
      setChatLoading(false);
    }
  };

  const handleClearChat = async () => {
    if (!selectedId || messages.length === 0) return;
    if (!confirm("Clear all chat messages for this document?")) return;
    setChatLoading(true);
    setError(null);
    try {
      await api.clearMessages(selectedId);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear chat");
    } finally {
      setChatLoading(false);
    }
  };

  const sendSuggestion = (text: string) => {
    setChatInput(text);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this document and all analyses?")) return;
    setLoading(true);
    try {
      await api.deleteDocument(id);
      const docs = await loadDocuments();
      if (selectedId === id) {
        if (docs[0]) {
          await selectDocument(docs[0].id);
        } else {
          setSelectedId(null);
          sessionStorage.removeItem(SELECTED_DOC_KEY);
          setAnalysis(null);
          setAnalysisHistory([]);
          setMessages([]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  };

  const exportAnalysis = () => {
    if (!analysis || !selected) return;
    const blob = new Blob([JSON.stringify({ document: selected.title, analysis }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selected.title.replace(/\s+/g, "-")}-analysis.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setDocuments([]);
    setSelectedId(null);
    setMessages([]);
    setAnalysis(null);
    setAnalysisHistory([]);
    sessionStorage.removeItem(SELECTED_DOC_KEY);
  };

  const handleAuth = async (authedUser: User) => {
    setUser(authedUser);
    setError(null);
    try {
      const docs = await loadDocuments();
      const raw = sessionStorage.getItem(SELECTED_DOC_KEY);
      if (raw) {
        const id = Number(raw);
        if (docs.some((d) => d.id === id)) {
          await selectDocument(id);
        }
      }
    } catch (e) {
      setError(String(e));
    }
  };

  if (authLoading) {
    return (
      <div className="auth-page">
        <p className="auth-loading">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return <AuthPage onAuth={handleAuth} />;
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <h1>MindForge</h1>
            <p className="tagline">RAG-powered text analysis & contextual chat</p>
          </div>
        </div>
        {health && (
          <div className="header-badges">
            <div className="health-badge mono user-badge">{user.email}</div>
            <div className="health-badge mono">
              <span className="dot dot-on" />
              {health.features.llm_enabled
                ? `LLM · ${health.features.llm_provider}`
                : "Local NLP"}
            </div>
            {health.features.rag_tfidf && (
              <div className="health-badge mono feature-badge">
                {health.features.retrieval_mode === "hybrid"
                  ? "RAG · Hybrid (TF-IDF + MiniLM)"
                  : "RAG · TF-IDF"}
              </div>
            )}
            {health.features.vector_store && (
              <div className="health-badge mono feature-badge">
                Vector DB · {health.features.vector_store_backend ?? "Chroma"}
              </div>
            )}
            {health.features.llm_enabled && health.features.llm_model && (
              <div className="health-badge mono feature-badge">
                Gen · {health.features.llm_model}
              </div>
            )}
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
              Log out
            </button>
          </div>
        )}
      </header>

      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button type="button" className="dismiss" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      <div className="layout">
        <aside className="sidebar">
          <h2>Documents</h2>
          <ul className="doc-list">
            {documents.length === 0 && (
              <li className="empty">No documents yet — create one →</li>
            )}
            {documents.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  className={`doc-item ${selectedId === doc.id ? "active" : ""}`}
                  onClick={() => selectDocument(doc.id)}
                >
                  <span className="doc-title">{doc.title}</span>
                  <span className="doc-meta">
                    {doc.source_type === "upload" ? "📄 " : ""}
                    {doc.chunk_count} chunks · {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                </button>
                <button
                  type="button"
                  className="btn btn-danger doc-delete"
                  onClick={() => handleDelete(doc.id)}
                  title="Delete"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>

          <form className="create-form" onSubmit={handleCreate}>
            <h2>New document</h2>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title"
              required
            />
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste your text here (min 10 characters)..."
              rows={6}
              required
            />
            <p className={`char-count ${content.trim().length < 10 ? "char-count-warn" : ""}`}>
              {content.trim().length} / 10 characters minimum
            </p>
            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving || content.trim().length < 10 || !title.trim()}
              >
                {saving ? "Saving…" : "Save document"}
              </button>
              <label className={`btn btn-ghost upload-btn ${saving ? "disabled" : ""}`}>
                Upload .txt/.md
                <input
                  ref={fileRef}
                  type="file"
                  accept=".txt,.md,.csv"
                  onChange={handleUpload}
                  hidden
                  disabled={saving}
                />
              </label>
            </div>
          </form>
        </aside>

        <main className="main">
          {!selected ? (
            <div className="placeholder">
              <h2>Welcome</h2>
              <p>
                Create or upload a document, run AI analysis, then chat with RAG — the
                system retrieves the most relevant chunks before answering.
              </p>
              <ul>
                <li>Hybrid RAG — TF-IDF + sentence embeddings (MiniLM)</li>
                <li>Readability & document metrics</li>
                <li>Analysis history & JSON export</li>
                <li>100% local NLP — no API keys required</li>
              </ul>
            </div>
          ) : (
            <>
              <section className="panel doc-panel">
                <div className="panel-head">
                  <div>
                    <h2>{selected.title}</h2>
                    {selected.file_name && (
                      <span className="file-label mono">{selected.file_name}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleAnalyze}
                    disabled={loading}
                  >
                    {loading ? "Working…" : "Run AI analysis"}
                  </button>
                </div>
                <p className={`doc-content ${docExpanded ? "doc-content-expanded" : ""}`}>
                  {selected.content}
                </p>
                {selected.content.length > 320 && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm doc-toggle"
                    onClick={() => setDocExpanded((v) => !v)}
                  >
                    {docExpanded ? "Show less" : "Show full text"}
                  </button>
                )}
              </section>

              {!analysis && (
                <section className="panel nudge-panel">
                  <p>
                    Run AI analysis to see summary, sentiment, keywords, and metrics.
                  </p>
                </section>
              )}

              {analysis?.metrics && (
                <section className="panel metrics-panel">
                  <h2>Document metrics</h2>
                  <div className="metrics-grid">
                    <div className="metric">
                      <span className="metric-value">{analysis.metrics.word_count}</span>
                      <span className="metric-label">Words</span>
                    </div>
                    <div className="metric">
                      <span className="metric-value">{analysis.metrics.unique_words}</span>
                      <span className="metric-label">Unique</span>
                    </div>
                    <div className="metric">
                      <span className="metric-value">{analysis.metrics.sentence_count}</span>
                      <span className="metric-label">Sentences</span>
                    </div>
                    <div className="metric">
                      <span className="metric-value">{analysis.metrics.reading_time_min}m</span>
                      <span className="metric-label">Read time</span>
                    </div>
                    {analysis.metrics.readability_grade != null && (
                      <div className="metric">
                        <span className="metric-value">{analysis.metrics.readability_grade}</span>
                        <span className="metric-label">Grade level</span>
                      </div>
                    )}
                    {analysis.metrics.flesch_reading_ease != null && (
                      <div className="metric">
                        <span className="metric-value">{analysis.metrics.flesch_reading_ease}</span>
                        <span className="metric-label">Flesch ease</span>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {analysis && (
                <section className="panel analysis-panel">
                  <div className="panel-head">
                    <h2>Analysis</h2>
                    <div className="panel-actions">
                      <span className="mono provider">via {analysis.provider}</span>
                      <button type="button" className="btn btn-ghost" onClick={exportAnalysis}>
                        Export JSON
                      </button>
                    </div>
                  </div>
                  <div className="sentiment-bar-wrap">
                    <div className="sentiment-bar-label">
                      Sentiment spectrum
                      <span className={`chip ${sentimentClass(analysis.sentiment)}`}>
                        {analysis.sentiment}
                      </span>
                    </div>
                    <div className="sentiment-bar">
                      <div
                        className="sentiment-marker"
                        style={{ left: `${scoreToPercent(analysis.sentiment_score)}%` }}
                        title={analysis.sentiment_score.toFixed(3)}
                      />
                    </div>
                  </div>
                  <div className="analysis-grid">
                    <div className="card">
                      <h3>Summary</h3>
                      <p>{analysis.summary}</p>
                    </div>
                    <div className="card">
                      <h3>Keywords</h3>
                      <div className="tags">
                        {analysis.keywords.map((k) => (
                          <span key={k} className="tag">
                            {k}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="card">
                      <h3>Topics</h3>
                      <div className="tags">
                        {analysis.topics.map((t) => (
                          <span key={t} className="tag topic">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="card">
                      <h3>Subjectivity</h3>
                      <p className="score mono">
                        {analysis.metrics
                          ? analysis.metrics.subjectivity.toFixed(3)
                          : "—"}{" "}
                        (0 = objective, 1 = subjective)
                      </p>
                    </div>
                  </div>

                  {analysisHistory.length > 1 && (
                    <div className="history-block">
                      <h3>Analysis history</h3>
                      <ul className="history-list">
                        {analysisHistory.map((a) => (
                          <li key={a.id}>
                            <button
                              type="button"
                              className={`history-item ${a.id === analysis.id ? "active" : ""}`}
                              onClick={() => setAnalysis(a)}
                            >
                              <span>{new Date(a.created_at).toLocaleString()}</span>
                              <span className={`chip ${sentimentClass(a.sentiment)}`}>
                                {a.sentiment} ({a.sentiment_score.toFixed(2)})
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </section>
              )}

              <section className="panel chat-panel">
                <div className="panel-head chat-panel-head">
                  <h2>RAG chat</h2>
                  {messages.length > 0 && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={handleClearChat}
                      disabled={chatLoading}
                    >
                      Clear chat
                    </button>
                  )}
                </div>
                <p className="rag-note">
                  {health?.features.retrieval_mode === "hybrid"
                    ? "Hybrid retrieval (TF-IDF + MiniLM)"
                    : "TF-IDF retrieval"}
                  {health?.features.vector_store
                    ? ` · vectors in ${health.features.vector_store_backend ?? "ChromaDB"}`
                    : " · vectors computed on the fly"}
                  {" · "}
                  {health?.features.llm_enabled
                    ? `LLM answers (${health.features.llm_provider})`
                    : "Extractive answers (no LLM)"}
                  {" · "}
                  {selected.chunk_count} chunk
                  {selected.chunk_count === 1 ? "" : "s"}
                </p>
                {health?.features.storage_mode === "ephemeral" && (
                  <p className="rag-note rag-note-warn">
                    Demo uses temporary storage — connect PostgreSQL on Render for persistent data.
                  </p>
                )}
                {health?.features.storage_mode === "persistent" && (
                  <p className="rag-note rag-note-ok">
                    Your documents and chats are saved to your account.
                  </p>
                )}
                <div className="chat-suggestions">
                  {CHAT_SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="suggestion-chip"
                      onClick={() => sendSuggestion(s)}
                      disabled={chatLoading || loading}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <div className="chat-messages">
                  {messages.length === 0 && !chatLoading && (
                    <p className="chat-hint">Tap a suggestion above or type your question.</p>
                  )}
                  {messages.map((m) => (
                    <div key={m.id} className={`bubble bubble-${m.role}`}>
                      <span className="bubble-role">
                        {m.role}
                        {m.rag_chunks_used ? ` · ${m.rag_chunks_used} chunks` : ""}
                      </span>
                      <p className="bubble-text">{m.content}</p>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="bubble bubble-assistant bubble-typing">
                      <span className="bubble-role">assistant</span>
                      <p className="chat-hint">Thinking…</p>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
                <form
                  className="chat-form"
                  onSubmit={handleChat}
                >
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a question about the document…"
                    disabled={chatLoading || loading}
                  />
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={chatLoading || loading || !chatInput.trim()}
                  >
                    Send
                  </button>
                </form>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
