import { useEffect, useState } from "react";
import { api } from "../api.js";

const CATEGORIES = ["general", "press", "social", "editorial", "retail", "product", "newsletter", "ad"];
const ACCEPT = ".txt,.md,.pdf,.docx,.doc";

const blank = { title: "", category: "general", content: "", active: true };

// Edit this single line to change who maintainers are told to contact.
const SUPPORT_CONTACT =
  "Questions about model choice or scaling the document set? Reach out to SportsTech.";

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("text"); // "text" | "upload"
  const [form, setForm] = useState(blank);
  const [file, setFile] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [list, st] = await Promise.all([
        api.listDocuments(),
        api.getContextStatus(),
      ]);
      setDocs(list);
      setStatus(st);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function resetForm() {
    setForm(blank);
    setFile(null);
    setEditingId(null);
  }

  async function save() {
    setError("");
    setBusy(true);
    try {
      if (mode === "upload" && !editingId) {
        if (!file || !form.title.trim()) return;
        const fd = new FormData();
        fd.append("file", file);
        fd.append("title", form.title);
        fd.append("category", form.category);
        fd.append("active", String(form.active));
        await api.uploadDocument(fd);
      } else {
        if (!form.title.trim() || !form.content.trim()) return;
        if (editingId) {
          await api.updateDocument(editingId, form);
        } else {
          await api.createDocument(form);
        }
      }
      resetForm();
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function edit(doc) {
    setMode("text");
    setEditingId(doc.id);
    setFile(null);
    setForm({ title: doc.title, category: doc.category, content: doc.content, active: doc.active });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function toggle(doc) {
    try {
      await api.updateDocument(doc.id, { active: !doc.active });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(id) {
    if (!confirm("Delete this reference document?")) return;
    try {
      await api.deleteDocument(id);
      if (editingId === id) resetForm();
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function download(doc) {
    try {
      const { url } = await api.downloadDocument(doc.id);
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setError(e.message);
    }
  }

  const canSave =
    mode === "upload" && !editingId
      ? !!file && !!form.title.trim()
      : !!form.title.trim() && !!form.content.trim();

  return (
    <div className="single">
      <div className="pane-label">
        {editingId ? "Edit reference document" : "Add reference document"}
      </div>
      {error && <div className="err">{error}</div>}

      {!editingId && (
        <div className="mode-tabs">
          <button
            className={`mode-tab ${mode === "text" ? "active" : ""}`}
            onClick={() => { setMode("text"); setFile(null); }}
          >
            Paste text
          </button>
          <button
            className={`mode-tab ${mode === "upload" ? "active" : ""}`}
            onClick={() => setMode("upload")}
          >
            Upload file
          </button>
        </div>
      )}

      <div className="form-grid">
        <div className="field">
          <span className="pane-label">Title</span>
          <input
            type="text"
            value={form.title}
            placeholder="e.g. Kipchoge Berlin caption"
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </div>
        <div className="field">
          <span className="pane-label">Category</span>
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {mode === "upload" && !editingId ? (
        <div className="field">
          <span className="pane-label">File (.txt, .md, .pdf, .docx, .doc)</span>
          <input
            type="file"
            accept={ACCEPT}
            onChange={(e) => {
              const f = e.target.files?.[0] || null;
              setFile(f);
              // Default the title to the filename (without extension) if empty.
              if (f && !form.title.trim()) {
                setForm({ ...form, title: f.name.replace(/\.[^.]+$/, "") });
              }
            }}
          />
          {file && <span className="doc-meta">{file.name} · {Math.ceil(file.size / 1024)} KB</span>}
        </div>
      ) : (
        <div className="field">
          <span className="pane-label">Content</span>
          <textarea
            style={{ minHeight: 160 }}
            value={form.content}
            placeholder="Paste exemplar copy that captures the Maurten voice."
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
        </div>
      )}

      <div className="controls">
        <label className="toggle">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm({ ...form, active: e.target.checked })}
          />
          Include in model context
        </label>
        {editingId && (
          <button className="reset-btn" onClick={resetForm}>
            Cancel
          </button>
        )}
        <button className="btn" onClick={save} disabled={!canSave || busy}>
          {busy ? "Working…" : editingId ? "Update" : mode === "upload" ? "Upload" : "Add"}
        </button>
      </div>

      <div className="pane-label" style={{ marginTop: 8 }}>
        Corpus ({docs.filter((d) => d.active).length} active / {docs.length} total)
      </div>

      <ContextStatusPanel status={status} />

      {loading ? (
        <div className="spinner">Loading…</div>
      ) : (
        <div className="doc-list">
          {docs.length === 0 && <div className="empty-text">No documents yet</div>}
          {docs.map((doc) => (
            <div key={doc.id} className={`doc-row ${doc.active ? "" : "inactive"}`}>
              <span className="doc-cat">{doc.category}</span>
              <span className="doc-title">
                {doc.title}
                {doc.source_type === "upload" && <span className="doc-badge">file</span>}
              </span>
              <span className="doc-meta">{doc.content.length} chars</span>
              <div className="doc-actions">
                {doc.has_file && (
                  <button className="reset-btn" onClick={() => download(doc)}>Download</button>
                )}
                <button className="reset-btn" onClick={() => toggle(doc)}>
                  {doc.active ? "Deactivate" : "Activate"}
                </button>
                <button className="reset-btn" onClick={() => edit(doc)}>Edit</button>
                <button className="reset-btn" onClick={() => remove(doc.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const LEVEL_COPY = {
  ok: { badge: "Healthy", tone: "the current approach is the right choice" },
  review: {
    badge: "Review recommended",
    tone: "approaching the limit of the send-every-document approach",
  },
  act: {
    badge: "Action needed",
    tone: "the corpus has outgrown the send-every-document approach",
  },
};

const fmt = (n) => Number(n || 0).toLocaleString();

// Persistent corpus-health panel. Always shown — it explains the current state
// (including when everything is healthy) so maintainers know when, and why, the
// implementation approach should change. Level + thresholds come from the
// backend (voice.context_status); the copy lives here.
function ContextStatusPanel({ status }) {
  if (!status) return null;
  const copy = LEVEL_COPY[status.level] || LEVEL_COPY.ok;
  return (
    <div className={`ctx-status ctx-${status.level}`}>
      <div className="ctx-head">
        <span className="ctx-badge">{copy.badge}</span>
        <span className="ctx-tone">{copy.tone}</span>
      </div>

      <div className="ctx-metrics">
        {status.active_docs} active docs · {fmt(status.active_chars)} /{" "}
        {fmt(status.max_context_chars)} chars ({status.fill_pct}% of context budget)
      </div>

      {status.dropped_count > 0 && (
        <div className="ctx-dropped">
          {status.dropped_count} document
          {status.dropped_count > 1 ? "s" : ""} currently dropped from the model
          context: {status.dropped_titles.join(", ")}
        </div>
      )}

      <div className="ctx-models">
        Review model: <b>{status.review_model}</b> · Rewrite model:{" "}
        <b>{status.rewrite_model}</b>
        {status.level === "ok" && " — appropriate for a corpus of this size."}
      </div>

      <div className="ctx-explain">
        Every active reference document is sent to the model on each review and
        rewrite, as examples of the Maurten voice. The "context budget" is the
        most reference text that can be sent at once. As the corpus approaches
        the budget, each review costs and takes a little more; once it exceeds
        the budget, documents at the bottom of the list are dropped from the
        model's context. That is the point to switch from sending every document
        to a distilled "voice spec" — a compact summary plus a few canonical
        examples — which keeps the whole voice in play without growing the prompt.
      </div>

      <div className="ctx-contact">{SUPPORT_CONTACT}</div>
    </div>
  );
}
