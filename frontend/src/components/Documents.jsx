import { useEffect, useState } from "react";
import { api } from "../api.js";

const CATEGORIES = ["general", "press", "social", "editorial", "retail", "product", "newsletter", "ad"];

const blank = { title: "", category: "general", content: "", active: true };

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setDocs(await api.listDocuments());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function save() {
    if (!form.title.trim() || !form.content.trim()) return;
    setError("");
    try {
      if (editingId) {
        await api.updateDocument(editingId, form);
      } else {
        await api.createDocument(form);
      }
      setForm(blank);
      setEditingId(null);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function edit(doc) {
    setEditingId(doc.id);
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
      if (editingId === id) { setForm(blank); setEditingId(null); }
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="single">
      <div className="pane-label">
        {editingId ? "Edit reference document" : "Add reference document"}
      </div>
      {error && <div className="err">{error}</div>}

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

      <div className="field">
        <span className="pane-label">Content</span>
        <textarea
          style={{ minHeight: 160 }}
          value={form.content}
          placeholder="Paste exemplar copy that captures the Maurten voice."
          onChange={(e) => setForm({ ...form, content: e.target.value })}
        />
      </div>

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
          <button className="reset-btn" onClick={() => { setForm(blank); setEditingId(null); }}>
            Cancel
          </button>
        )}
        <button className="btn" onClick={save} disabled={!form.title.trim() || !form.content.trim()}>
          {editingId ? "Update" : "Add"}
        </button>
      </div>

      <div className="pane-label" style={{ marginTop: 8 }}>
        Corpus ({docs.filter((d) => d.active).length} active / {docs.length} total)
      </div>

      {loading ? (
        <div className="spinner">Loading…</div>
      ) : (
        <div className="doc-list">
          {docs.length === 0 && <div className="empty-text">No documents yet</div>}
          {docs.map((doc) => (
            <div key={doc.id} className={`doc-row ${doc.active ? "" : "inactive"}`}>
              <span className="doc-cat">{doc.category}</span>
              <span className="doc-title">{doc.title}</span>
              <span className="doc-meta">{doc.content.length} chars</span>
              <div className="doc-actions">
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
