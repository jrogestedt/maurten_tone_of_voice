import { useState } from "react";
import Reviewer from "./components/Reviewer.jsx";
import Documents from "./components/Documents.jsx";
import VoiceConfig from "./components/VoiceConfig.jsx";

export default function App() {
  const [tab, setTab] = useState("reviewer");

  return (
    <>
      <div className="header">
        <span className="header-logo">M.</span>
        <span className="header-divider">/</span>
        <span className="header-title">Brand Voice Reviewer</span>
        <span className="header-tag">Head of Copy</span>
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
