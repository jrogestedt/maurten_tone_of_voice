import { useEffect, useState } from "react";
import Reviewer from "./components/Reviewer.jsx";
import Documents from "./components/Documents.jsx";
import VoiceConfig from "./components/VoiceConfig.jsx";
import Login from "./components/Login.jsx";
import { isLoggedIn, getEmail, clearSession, onAuthChange } from "./auth.js";

export default function App() {
  const [tab, setTab] = useState("reviewer");
  const [authed, setAuthed] = useState(isLoggedIn());

  // Re-render whenever the session changes (login, logout, or a 401 clears it).
  useEffect(() => onAuthChange(() => setAuthed(isLoggedIn())), []);

  if (!authed) return <Login />;

  return (
    <>
      <div className="header">
        <span className="header-logo">M.</span>
        <span className="header-divider">/</span>
        <span className="header-title">Brand Voice Reviewer</span>
        <span className="header-tag">Head of Copy</span>
        <span className="header-user">{getEmail()}</span>
        <button className="header-logout" onClick={clearSession}>
          Sign out
        </button>
      </div>

      <div className="nav">
        <button className={tab === "reviewer" ? "active" : ""} onClick={() => setTab("reviewer")}>
          Reviewer
        </button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
          Reference Docs
        </button>
        <button className={tab === "voice" ? "active" : ""} onClick={() => setTab("voice")}>
          Voice Config
        </button>
      </div>

      {tab === "reviewer" && <Reviewer />}
      {tab === "documents" && <Documents />}
      {tab === "voice" && <VoiceConfig />}
    </>
  );
}
