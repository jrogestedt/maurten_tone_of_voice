// Minimal session store: one JWT in localStorage, no refresh tokens.
const KEY_TOKEN = "maurten.auth.token";
const KEY_EMAIL = "maurten.auth.email";

const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn());

export function onAuthChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getToken() {
  return localStorage.getItem(KEY_TOKEN);
}

export function getEmail() {
  return localStorage.getItem(KEY_EMAIL) || "";
}

export function isLoggedIn() {
  return !!getToken();
}

export function setSession(token, email) {
  localStorage.setItem(KEY_TOKEN, token);
  if (email) localStorage.setItem(KEY_EMAIL, email);
  emit();
}

export function clearSession() {
  localStorage.removeItem(KEY_TOKEN);
  localStorage.removeItem(KEY_EMAIL);
  emit();
}
