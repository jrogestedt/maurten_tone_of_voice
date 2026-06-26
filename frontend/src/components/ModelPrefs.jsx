import { useEffect, useState } from "react";
import { api } from "../api.js";

const usd = (n) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

// Output tokens dominate per-call cost, so compare options on output rate.
// Returns a multiplier relative to the cheapest option's output rate.
function outputMultiplier(option, options) {
  const rates = options.map((o) => o.output_per_mtok).filter((r) => r != null);
  const min = Math.min(...rates);
  if (!option.output_per_mtok || !min) return null;
  return option.output_per_mtok / min;
}

export default function ModelPrefs() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getModelPreferences()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function pick(role, modelId) {
    if (!data || saving) return;
    const next = {
      review_model: role === "review" ? modelId : data.review_model,
      rewrite_model: role === "rewrite" ? modelId : data.rewrite_model,
    };
    if (
      next.review_model === data.review_model &&
      next.rewrite_model === data.rewrite_model
    )
      return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateModelPreferences(
        next.review_model,
        next.rewrite_model
      );
      setData(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="single">
      <div className="pane-label">Model selection</div>
      <div className="step-label">
        Choose which Claude model your reviews and rewrites run on. This is{" "}
        <span>your personal setting</span> — it affects only your account and is
        remembered across sessions. Output tokens dominate per-review cost, so the
        output rate is the number that matters most.
      </div>

      {error && <div className="err">{error}</div>}
      {loading ? (
        <div className="spinner">Loading…</div>
      ) : data ? (
        <>
          <Selector
            role="review"
            title="Review model"
            hint="The nuanced voice judgment — quality matters most here."
            selected={data.review_model}
            options={data.options}
            onPick={pick}
            disabled={saving}
          />
          <Selector
            role="rewrite"
            title="Rewrite model"
            hint="Applies the voice to produce revised copy."
            selected={data.rewrite_model}
            options={data.options}
            onPick={pick}
            disabled={saving}
          />

          <div className="controls">
            {saving && <span className="spinner">Saving…</span>}
            {saved && <span className="saved">Saved</span>}
            {data.is_default && !saving && !saved && (
              <span className="model-default-note">Using the team defaults</span>
            )}
          </div>

          <CostTable options={data.options} />
        </>
      ) : null}
    </div>
  );
}

function Selector({ role, title, hint, selected, options, onPick, disabled }) {
  return (
    <div className="model-group">
      <div className="model-group-head">
        <span className="model-group-title">{title}</span>
        <span className="model-group-hint">{hint}</span>
      </div>
      <div className="model-options">
        {options.map((o) => {
          const mult = outputMultiplier(o, options);
          const active = o.id === selected;
          return (
            <button
              key={o.id}
              className={`model-option ${active ? "active" : ""}`}
              onClick={() => onPick(role, o.id)}
              disabled={disabled}
              type="button"
            >
              <span className="model-option-label">{o.label}</span>
              <span className="model-option-tier">{o.tier}</span>
              <span className="model-option-price">
                {usd(o.input_per_mtok)} in · {usd(o.output_per_mtok)} out
                <span className="model-option-unit"> / M tokens</span>
              </span>
              {mult != null && (
                <span className="model-option-mult">
                  {mult === 1 ? "cheapest output" : `${mult.toFixed(1)}× output cost`}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Plain comparison so the cost difference is explicit, not just per-button.
function CostTable({ options }) {
  return (
    <div className="usage-table-wrap">
      <div className="divider">Cost comparison ($ per million tokens)</div>
      <table className="usage-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Input</th>
            <th>Output</th>
            <th>Relative output</th>
          </tr>
        </thead>
        <tbody>
          {options.map((o) => {
            const mult = outputMultiplier(o, options);
            return (
              <tr key={o.id}>
                <td className="usage-key">{o.label}</td>
                <td>{usd(o.input_per_mtok)}</td>
                <td className="usage-cost">{usd(o.output_per_mtok)}</td>
                <td>{mult == null ? "—" : `${mult.toFixed(1)}×`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
