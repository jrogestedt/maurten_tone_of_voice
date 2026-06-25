import { useEffect, useState } from "react";
import { api } from "../api.js";

const usd = (n) =>
  `$${Number(n || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const num = (n) => Number(n || 0).toLocaleString();

// Compact token display: 1234 -> "1.2k", 1500000 -> "1.5M".
function tokens(n) {
  n = Number(n || 0);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function sinceLabel(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function Usage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    api
      .getUsage()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="single">
      <div className="usage-head">
        <div>
          <div className="pane-label">Usage &amp; cost</div>
          <div className="step-label">
            Token usage and estimated spend across every review and rewrite.
            Costs are computed from Anthropic's published per-token rates
            (cache writes at the 1-hour rate). Estimate, not a billing figure.
          </div>
        </div>
        <button className="reset-btn" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <div className="err">{error}</div>}
      {loading && <div className="spinner">Loading…</div>}

      {data && !loading && (
        <>
          <div className="usage-cards">
            <div className="usage-card">
              <div className="usage-card-val">{usd(data.total_cost_usd)}</div>
              <div className="usage-card-label">Total cost (est.)</div>
            </div>
            <div className="usage-card">
              <div className="usage-card-val">{num(data.total_calls)}</div>
              <div className="usage-card-label">API calls</div>
            </div>
            <div className="usage-card">
              <div className="usage-card-val">{tokens(data.total_tokens)}</div>
              <div className="usage-card-label">Total tokens</div>
            </div>
            <div className="usage-card">
              <div className="usage-card-val">
                {tokens(data.total_output_tokens)}
              </div>
              <div className="usage-card-label">Output tokens</div>
            </div>
          </div>

          <div className="usage-since">
            Tracking since {sinceLabel(data.since)}
          </div>

          <Breakdown title="By model" rows={data.by_model} />
          <Breakdown title="By operation" rows={data.by_operation} />

          <div className="usage-foot">
            Cache: {tokens(data.total_cache_read_input_tokens)} read /{" "}
            {tokens(data.total_cache_creation_input_tokens)} written.
            Reads bill at ~10% of input — high read volume means caching is working.
          </div>
        </>
      )}
    </div>
  );
}

function Breakdown({ title, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="usage-table-wrap">
      <div className="divider">{title}</div>
      <table className="usage-table">
        <thead>
          <tr>
            <th>{title.replace("By ", "")}</th>
            <th>Calls</th>
            <th>Input</th>
            <th>Cache R/W</th>
            <th>Output</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="usage-key">{r.key}</td>
              <td>{num(r.calls)}</td>
              <td>{tokens(r.input_tokens)}</td>
              <td>
                {tokens(r.cache_read_input_tokens)} /{" "}
                {tokens(r.cache_creation_input_tokens)}
              </td>
              <td>{tokens(r.output_tokens)}</td>
              <td className="usage-cost">{usd(r.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
