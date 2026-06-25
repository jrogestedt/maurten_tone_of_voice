import { getToken, clearSession } from "./auth.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "";

async function req(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    // Token missing/expired — drop the session so the app shows the login screen.
    clearSession();
  }
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
  // --- Auth ---
  requestCode: (email) =>
    req("/api/auth/request-code", { method: "POST", body: JSON.stringify({ email }) }),
  verifyCode: (email, code) =>
    req("/api/auth/verify-code", { method: "POST", body: JSON.stringify({ email, code }) }),
  me: () => req("/api/auth/me"),

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
