import React from "react";
import type { TestResult } from "../../../hooks/useTestPrompt";

function fmt(n: number): string {
  return n.toLocaleString();
}

interface Props {
  result: TestResult;
  onClear: () => void;
}

export const ResultCard: React.FC<Props> = ({ result, onClear }) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.response);
    } catch {
      // ignore — clipboard may be unavailable in some contexts
    }
  };
  return (
    <div
      className="sm-result-card"
      role="region"
      aria-label="Test prompt result"
    >
      <dl className="sm-result-stats">
        <div>
          <dt>TTFT</dt>
          <dd>{fmt(result.ttftMs)}ms</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{fmt(result.totalMs)}ms</dd>
        </div>
        <div>
          <dt>In</dt>
          <dd>{fmt(result.tokensIn)}</dd>
        </div>
        <div>
          <dt>Out</dt>
          <dd>{fmt(result.tokensOut)}</dd>
        </div>
        <div>
          <dt>TPS</dt>
          <dd>{result.tps.toFixed(2)}</dd>
        </div>
      </dl>
      <pre className="sm-result-response" aria-label="Model response">
        {result.response}
      </pre>
      <div className="sm-result-actions">
        <button type="button" className="sm-btn-ghost" onClick={handleCopy}>
          Copy
        </button>
        <button type="button" className="sm-btn-ghost" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
};
