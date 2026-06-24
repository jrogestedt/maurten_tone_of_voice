import { useEffect, useState } from "react";
import { api } from "../api.js";

const INTENT_LABELS = {
  product: "Product-led",
  reactive: "Reactive moment",
  athlete: "Athlete story",
  education: "Education",
  brand: "Brand / awareness",
};
const FORMAT_LABELS = {
  general: "Any format",
  pdp: "Product page (PDP)",
  newsletter: "Newsletter",
  social: "Social / SoMe",
  ad: "Ad copy",
  press: "Press release",
  retail: "Retail guide",
  editorial: "Editorial / long-form",
};

export default function Reviewer() {
  const [copy, setCopy] = useState("");
  const [format, setFormat] = useState("general");
  const [intent, setIntent] = useState("product");

  const [review, setReview] = useState(null);
  const [rewrite, setRewrite] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [error, setError] = useState("");

  // Confirm the API is reachable; harmless if it fails.
  useEffect(() => {
    api.options().catch(() => {});
  }, []);

  async function runReview() {
    if (!copy.trim()) return;
    setLoading(true);
    setError("");
    setReview(null);
    setRewrite(null);
    try {
      const r = await api.review({ copy, format, intent });
      setReview(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function runRewrite() {
    if (!review) return;
    setRewriting(true);
    setError("");
    try {
      const issues = review.notes
        .filter((n) => n.flag === "red" || n.flag === "amber")
        .map((n) => `${n.issue}${n.fix ? ` Fix: ${n.fix}` : ""}`);
      const r = await api.rewrite({ copy, format, intent, issues });
      setRewrite(r.rewrite);
    } catch (e) {
      setError(e.message);
    } finally {
      setRewriting(false);
    }
  }

  function reset() {
    setCopy("");
    setReview(null);
    setRewrite(null);
    setError("");
  }

  const score = review?.score ?? 0;
  const col = score >= 8 ? "var(--green)" : score >= 5 ? "var(--amber)" : "var(--red)";
  const reds = review?.notes.filter((n) => n.flag === "red") || [];
  const ambers = review?.notes.filter((n) => n.flag === "amber") || [];
  const greens = review?.notes.filter((n) => n.flag === "green") || [];

  return (
    <div className="layout">
      <div className="pane pane-left">
        <div className="pane-label">Draft copy</div>
        <textarea
          id="input"
          placeholder="Paste draft copy here."
          value={copy}
          onChange={(e) => setCopy(e.target.value)}
        />
        <div className="selects">
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {Object.entries(FORMAT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select value={intent} onChange={(e) => setIntent(e.target.value)}>
            {Object.entries(INTENT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div className="controls">
          <span className="char-count">{copy.length} chars</span>
          <button className="btn" onClick={runReview} disabled={loading || !copy.trim()}>
            {loading ? "Reviewing…" : "Review"}
          </button>
        </div>
      </div>

      <div className="pane">
        <div className="pane-label">Editorial notes</div>

        {error && <div className="err">{error}</div>}

        {!review && !loading && !error && (
          <>
            <div className="step-label">
              1. Paste copy. Select <span>format</span> + <span>intent</span>.
              <br />2. Hit <span>Review</span>.
              <br />3. Get a verdict, notes, and an optional <span>rewrite</span>.
            </div>
            <div className="empty">
              <div className="empty-mark">—</div>
              <div className="empty-text">Awaiting results</div>
            </div>
          </>
        )}

        {loading && <div className="spinner">Reviewing against the Maurten voice…</div>}

        {review && (
          <>
            <div className="verdict">
              <div className="verdict-dot" style={{ background: col }} />
              <div>
                <div className="verdict-score" style={{ color: col }}>
                  {score}
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>/10</span>
                </div>
                <div className="verdict-sub">Voice score</div>
              </div>
              <div className="verdict-text">{review.verdict}</div>
            </div>

            <div className="notes">
              {reds.length > 0 && <div className="divider">Red lines</div>}
              {reds.map((n, i) => <Note key={`r${i}`} n={n} />)}
              {ambers.length > 0 && <div className="divider">Voice notes</div>}
              {ambers.map((n, i) => <Note key={`a${i}`} n={n} />)}
              {greens.length > 0 && <div className="divider">What's working</div>}
              {greens.map((n, i) => <Note key={`g${i}`} n={n} />)}
            </div>

            <div className="action-row">
              <button className="reset-btn" onClick={reset}>New review</button>
              <button className="btn-sec" onClick={runRewrite} disabled={rewriting}>
                {rewriting ? "Rewriting…" : "Rewrite"}
              </button>
            </div>

            {rewrite && (
              <>
                <div className="rewrite-label">Rewrite</div>
                <div className="rewrite-box">{rewrite}</div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Note({ n }) {
  return (
    <div className={`note ${n.flag}`}>
      <span className="tag">{n.type}</span>
      <div>
        {n.quote && <div className="note-quote">"{n.quote}"</div>}
        <div className="note-text">{n.issue}</div>
        {n.fix && <div className="note-fix">Try: {n.fix}</div>}
      </div>
    </div>
  );
}
