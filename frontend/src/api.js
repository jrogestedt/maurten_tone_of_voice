import { getToken, clearSession } from "./auth.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "";

async function req(path, options = {}) {
  const token = getToken();
  // For FormData bodies, let the browser set Content-Type (with the multipart
  // boundary) — forcing application/json would break the upload.
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    // Token missing/expired — drop the session so the app shows the login screen.
    clearSession();
  }

  // Read the body as text first so we can give a clear error when the server
  // returns HTML (e.g. wrong port / backend down) instead of JSON.
  const text = await res.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      // The API always returns JSON. A non-JSON body — even on a 200 — means the
      // request didn't reach the backend at all: almost always the frontend is
      // calling its own origin (VITE_API_BASE_URL missing/wrong) and the static
      // server returned index.html. Fail loudly instead of treating it as success.
      throw new Error(
        res.ok
          ? `The API returned a non-JSON response (HTTP ${res.status}). The app is calling the wrong address — set VITE_API_BASE_URL to the backend URL and rebuild the frontend.`
          : `Server returned an unexpected response (HTTP ${res.status}). Is the API reachable?`
      );
    }
  }

  if (!res.ok) {
    throw new Error((body && body.detail) || res.statusText || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return body;
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
  getContextStatus: () => req("/api/documents/context-status"),
  createDocument: (payload) =>
    req("/api/documents", { method: "POST", body: JSON.stringify(payload) }),
  uploadDocument: (formData) =>
    req("/api/documents/upload", { method: "POST", body: formData }),
  updateDocument: (id, payload) =>
    req(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDocument: (id) => req(`/api/documents/${id}`, { method: "DELETE" }),
  downloadDocument: (id) => req(`/api/documents/${id}/download`),

  getVoiceConfig: () => req("/api/voice-config"),
  updateVoiceConfig: (prompt) =>
    req("/api/voice-config", { method: "PUT", body: JSON.stringify({ prompt }) }),

  getUsage: () => req("/api/usage"),

  getModelPreferences: () => req("/api/model-preferences"),
  updateModelPreferences: (review_model, rewrite_model) =>
    req("/api/model-preferences", {
      method: "PUT",
      body: JSON.stringify({ review_model, rewrite_model }),
    }),
};
