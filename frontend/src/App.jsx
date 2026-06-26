import { useEffect, useState } from "react";
import Reviewer from "./components/Reviewer.jsx";
import Documents from "./components/Documents.jsx";
import VoiceConfig from "./components/VoiceConfig.jsx";
import Usage from "./components/Usage.jsx";
import ModelPrefs from "./components/ModelPrefs.jsx";
import Guide from "./components/Guide.jsx";
import Login from "./components/Login.jsx";
import { isLoggedIn, clearSession, onAuthChange } from "./auth.js";

export default function App() {
  const [tab, setTab] = useState("reviewer");
  const [authed, setAuthed] = useState(isLoggedIn());
  // Initial theme is applied pre-paint by the inline script in index.html.
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "dark"
  );

  // Re-render whenever the session changes (login, logout, or a 401 clears it).
  useEffect(() => onAuthChange(() => setAuthed(isLoggedIn())), []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (e) {}
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  if (!authed) return <Login />;

  return (
    <>
      <div className="header">
        <span className="header-logo">M.</span>
        <span className="header-divider">/</span>
        <span className="header-title">Brand Voice Reviewer</span>
        <button
          className="header-theme"
          onClick={toggleTheme}
          title="Toggle light / dark mode"
          aria-label="Toggle light / dark mode"
        >
          {theme === "light" ? "Dark" : "Light"}
        </button>
        <button className="header-logout" onClick={clearSession}>
          Sign out
        </button>
      </div>

      <div className="nav">
        <button className={tab === "guide" ? "active" : ""} onClick={() => setTab("guide")}>
          How to use
        </button>
        <button className={tab === "reviewer" ? "active" : ""} onClick={() => setTab("reviewer")}>
          Reviewer
        </button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
          Reference Docs
        </button>
        <button className={tab === "voice" ? "active" : ""} onClick={() => setTab("voice")}>
          Voice Config
        </button>
        <button className={tab === "model" ? "active" : ""} onClick={() => setTab("model")}>
          Model
        </button>
        <button className={tab === "usage" ? "active" : ""} onClick={() => setTab("usage")}>
          Usage
        </button>
      </div>

      {tab === "guide" && <Guide onStart={() => setTab("reviewer")} />}
      {tab === "reviewer" && <Reviewer />}
      {tab === "documents" && <Documents />}
      {tab === "voice" && <VoiceConfig />}
      {tab === "model" && <ModelPrefs />}
      {tab === "usage" && <Usage />}
    </>
  );
}
