const BASE = import.meta.env.VITE_API_BASE_URL || "";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  options: () => req("/api/options"),
  review: (payload) =>
    req("/api/review", { method: "POST", body: JSON.stringify(payload) }),
  rewrite: (payload) =>
    req("/api/rewrite", { method: "POST", body: JSON.stringify(payload) }),

  listDocuments: () => req("/api/documents"),
  createDocument: (payload) =>
    req("/api/documents", { method: "POST", body: JSON.stringify(payload) }),
  updateDocument: (id, payload) =>
    req(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDocument: (id) => req(`/api/documents/${id}`, { method: "DELETE" }),

  getVoiceConfig: () => req("/api/voice-config"),
  updateVoiceConfig: (prompt) =>
    req("/api/voice-config", { method: "PUT", body: JSON.stringify({ prompt }) }),
};
