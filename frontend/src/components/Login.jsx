import { useState } from "react";
import { api } from "../api.js";
import { setSession } from "../auth.js";

export default function Login() {
  const [step, setStep] = useState("email"); // "email" | "code"
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function sendCode(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.requestCode(email.trim());
      setStep("code");
    } catch (err) {
      setError(err.message || "Could not send code.");
    } finally {
      setLoading(false);
    }
  }

  async function verify(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.verifyCode(email.trim(), code.trim());
      setSession(res.access_token, res.email); // re-renders app into authed view
    } catch (err) {
      setError(err.message || "Invalid code.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-brand">
          <span className="header-logo">M.</span>
          <span className="header-divider">/</span>
          <span className="header-title">Brand Voice Reviewer</span>
        </div>

        {step === "email" && (
          <form onSubmit={sendCode} className="login-form">
            <p className="step-label">
              Sign in with your Maurten email. We'll send a one-time code.
            </p>
            <input
              type="email"
              placeholder="you@maurten.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              required
            />
            <button className="btn" type="submit" disabled={loading || !email}>
              {loading ? "Sending…" : "Send code"}
            </button>
          </form>
        )}

        {step === "code" && (
          <form onSubmit={verify} className="login-form">
            <p className="step-label">
              Enter the code sent to <strong>{email}</strong>.
            </p>
            <input
              type="text"
              inputMode="numeric"
              placeholder="6-digit code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
              required
            />
            <button className="btn" type="submit" disabled={loading || !code}>
              {loading ? "Verifying…" : "Verify & sign in"}
            </button>
            <button
              type="button"
              className="btn-sec"
              onClick={() => {
                setStep("email");
                setCode("");
                setError("");
              }}
              disabled={loading}
            >
              Use a different email
            </button>
          </form>
        )}

        {error && <div className="err">{error}</div>}
      </div>
    </div>
  );
}
