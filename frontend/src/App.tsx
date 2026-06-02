import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Analysis, ChatMessage, Document, Health } from "./types";
import "./App.css";

const SAMPLE_TEXT = `Artificial intelligence is transforming how we work, learn, and create. 
Modern language models can summarize documents, answer questions, and detect sentiment with remarkable accuracy.
This platform combines local NLP with optional cloud models, so you can experiment with AI pipelines even without an API key.
Upload any article, notes, or essay — then analyze it and chat about the content using RAG-powered retrieval.`;

function sentimentClass(s: string) {
  if (s === "positive") return "chip-positive";
  if (s === "negative") return "chip-negative";
  return "chip-neutral";
}

function scoreToPercent(score: number) {
  return Math.round(((score + 1) / 2) * 100);
}

export default function App() {
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
    loadDocuments().catch((e) => setError(String(e)));
  }, [loadDocuments]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const selectDocument = async (id: number) => {
    setSelectedId(id);
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
    setLoading(true);
    setError(null);
    try {
      const doc = await api.createDocument(title, content);
      await loadDocuments();
      setSelectedId(doc.id);
      setAnalysis(null);
      setAnalysisHistory([]);
      setMessages([]);
      await selectDocument(doc.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create document");
    } finally {
      setLoading(false);
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
    setLoading(true);
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
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this document and all analyses?")) return;
    setLoading(true);
    try {
      await api.deleteDocument(id);
      const docs = await loadDocuments();
      if (selectedId === id) {
        setSelectedId(docs[0]?.id ?? null);
        setAnalysis(null);
        setAnalysisHistory([]);
        setMessages([]);
        if (docs[0]) await selectDocument(docs[0].id);
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
            <div className="health-badge mono">
              <span className={`dot ${health.openai_configured ? "dot-on" : "dot-off"}`} />
              {health.ai_provider} mode
            </div>
            {health.features.rag_tfidf && (
              <div className="health-badge mono feature-badge">RAG · TF-IDF</div>
            )}
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
              minLength={10}
            />
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={loading}>
                Save document
              </button>
              <label className="btn btn-ghost upload-btn">
                Upload .txt/.md
                <input
                  ref={fileRef}
                  type="file"
                  accept=".txt,.md,.csv"
                  onChange={handleUpload}
                  hidden
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
                <li>TF-IDF semantic retrieval (RAG pipeline)</li>
                <li>Readability & document metrics</li>
                <li>Analysis history & JSON export</li>
                <li>Local NLP or OpenAI GPT</li>
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
                <p className="doc-content">{selected.content}</p>
              </section>

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
                <h2>RAG chat</h2>
                <p className="rag-note">
                  Each reply uses TF-IDF retrieval over {selected.chunk_count} indexed chunks.
                </p>
                <div className="chat-messages">
                  {messages.length === 0 && (
                    <p className="chat-hint">
                      Try: &quot;Summarize this&quot;, &quot;What is the sentiment?&quot;, or
                      &quot;What is the readability grade?&quot;
                    </p>
                  )}
                  {messages.map((m) => (
                    <div key={m.id} className={`bubble bubble-${m.role}`}>
                      <span className="bubble-role">
                        {m.role}
                        {m.rag_chunks_used ? ` · ${m.rag_chunks_used} chunks` : ""}
                      </span>
                      <p>{m.content}</p>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
                <form className="chat-form" onSubmit={handleChat}>
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a question about the document…"
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading || !chatInput.trim()}
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
