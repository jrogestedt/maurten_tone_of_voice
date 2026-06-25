export default function Guide({ onStart }) {
  return (
    <div className="single guide">
      <div className="pane-label">How to use</div>

      <p className="guide-lead">
        This is an internal tool for pressure-testing copy against the Maurten
        brand voice. Paste a draft, and a model running the Maurten "Head of
        Copy" persona scores it, flags where it drifts off-voice, and — on
        request — rewrites it. It is a second set of eyes, not a replacement for
        your judgement.
      </p>

      <div className="divider">The three tabs</div>
      <div className="guide-steps">
        <div className="guide-step">
          <span className="guide-num">01</span>
          <div>
            <div className="guide-step-title">Reviewer</div>
            <div className="guide-step-text">
              Where the work happens. Paste draft copy, tell it the{" "}
              <span>format</span> (PDP, newsletter, social, ad…) and the{" "}
              <span>intent</span> (product-led, athlete story, education…), then
              hit Review. You get a voice score out of 10, a verdict, and
              line-by-line notes split into red lines, voice notes, and what's
              already working. Hit Rewrite to get a corrected version that keeps
              your meaning but fixes the flagged issues.
            </div>
          </div>
        </div>

        <div className="guide-step">
          <span className="guide-num">02</span>
          <div>
            <div className="guide-step-title">Reference Docs</div>
            <div className="guide-step-text">
              The corpus the model reads as voice examples before every review.
              Add, edit, activate, or deactivate documents here. Only{" "}
              <span>active</span> documents are sent as context, so toggle off
              anything that no longer represents the voice.
            </div>
          </div>
        </div>

        <div className="guide-step">
          <span className="guide-num">03</span>
          <div>
            <div className="guide-step-title">Voice Config</div>
            <div className="guide-step-text">
              The core persona instructions — the system prompt the model adopts
              on every review and rewrite. Edit this to shift how strict or
              lenient the reviewer is, or to adjust the voice itself. Changes
              apply immediately to the next review.
            </div>
          </div>
        </div>
      </div>

      <div className="divider">Reading the results</div>
      <div className="guide-legend">
        <div className="guide-legend-row">
          <span className="guide-dot" style={{ background: "var(--red)" }} />
          <strong>Red lines</strong> — voice violations to fix before this ships.
        </div>
        <div className="guide-legend-row">
          <span className="guide-dot" style={{ background: "var(--amber)" }} />
          <strong>Voice notes</strong> — softer suggestions; use your judgement.
        </div>
        <div className="guide-legend-row">
          <span className="guide-dot" style={{ background: "var(--green)" }} />
          <strong>What's working</strong> — on-voice moments worth keeping.
        </div>
      </div>

      <div className="step-label">
        The score and notes are guidance, not a gate. Treat low scores as a
        prompt to look closer, and always read the rewrite critically before
        using it.
      </div>

      {onStart && (
        <div className="controls">
          <button className="btn" onClick={onStart}>
            Start a review
          </button>
        </div>
      )}
    </div>
  );
}
