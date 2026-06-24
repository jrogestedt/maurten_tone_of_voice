import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function VoiceConfig() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getVoiceConfig()
      .then((c) => setPrompt(c.prompt))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setError("");
    setSaved(false);
    try {
      const c = await api.updateVoiceConfig(prompt);
      setPrompt(c.prompt);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="single">
      <div className="pane-label">Core voice instructions (system prompt)</div>
      <div className="step-label">
        This is the persona the model adopts on every review and rewrite. Active
        reference documents are appended automatically as voice examples.
      </div>
      {error && <div className="err">{error}</div>}
      {loading ? (
        <div className="spinner">Loading…</div>
      ) : (
        <>
          <textarea
            style={{ minHeight: 360 }}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="controls">
            {saved && <span className="saved">Saved</span>}
            <button className="btn" onClick={save} disabled={!prompt.trim()}>
              Save
            </button>
          </div>
        </>
      )}
    </div>
  );
}
