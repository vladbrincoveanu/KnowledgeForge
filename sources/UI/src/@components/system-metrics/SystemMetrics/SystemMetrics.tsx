import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { llmConfigAPI, LLMConfigResponse } from "../../../services/api";
import { useLLMStats } from "../../../hooks/useLLMStats";
import { useTestPrompt, TestResult } from "../../../hooks/useTestPrompt";
import { ResultCard } from "./ResultCard";
import { isValidModelName } from "../../../schemas/modelName";
import "./SystemMetrics.scss";

const KNOWN_MODELS = [
  "MiniMax-M3",
  "MiniMax-M2.7",
  "anthropic/claude-sonnet-4-20250514",
  "anthropic/claude-haiku-4-5-20251001",
];

function formatNum(n: number): string {
  return n.toLocaleString();
}

function fmtTs(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const SystemMetrics: React.FC = () => {
  const { runs, totals, avgTps, clearStats, addRun } = useLLMStats();
  const { status, result, error, run, reset } = useTestPrompt();
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "ok" | "err">("idle");
  const [errMsg, setErrMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const lastAddedRef = useRef<TestResult | null>(null);

  useEffect(() => {
    llmConfigAPI
      .getConfig()
      .then((c) => {
        setConfig(c);
        setSelectedModel(c.model);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (status !== "ok" || !result) return;
    if (lastAddedRef.current === result) return;
    lastAddedRef.current = result;
    addRun({
      task_id: `test-${result.timestamp}`,
      model: result.model || config?.model || "unknown",
      tokens_in: result.tokensIn,
      tokens_out: result.tokensOut,
      tool_calls: 0,
      duration_s: result.totalMs / 1000,
      tps: result.tps,
    });
  }, [status, result, addRun, config?.model]);

  const handleSave = async () => {
    setSaveStatus("idle");
    setErrMsg("");
    try {
      const patch: Record<string, string> = {};
      if (apiKeyInput) patch.api_key = apiKeyInput;
      if (selectedModel !== config?.model) {
        if (!isValidModelName(selectedModel)) {
          setErrMsg(
            "Invalid model format. Use 'anthropic/<name>' or 'MiniMax-<version>'",
          );
          setSaveStatus("err");
          return;
        }
        patch.model = selectedModel;
      }
      if (!Object.keys(patch).length) return;
      const updated = await llmConfigAPI.updateConfig(patch);
      setConfig(updated);
      setApiKeyInput("");
      setSaveStatus("ok");
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? (e.response?.data?.detail ?? e.message)
        : e instanceof Error
          ? e.message
          : "Failed to save";
      setErrMsg(msg);
      setSaveStatus("err");
    }
  };

  const handleRunTest = async () => {
    const ta = document.getElementById(
      "test-prompt",
    ) as HTMLTextAreaElement | null;
    if (!ta) return;
    await run(ta.value, selectedModel);
  };

  if (loading) {
    return (
      <div className="system-metrics">
        <h2>System Metrics</h2>
        <p>Loading...</p>
      </div>
    );
  }

  const keySource = config?.api_key_source;
  const keyLabel = config?.api_key_set
    ? keySource === "override"
      ? "● override"
      : "● env"
    : "○ not set";

  return (
    <div className="system-metrics">
      <h2>System Metrics</h2>

      <section className="sm-section">
        <h3>LLM Configuration</h3>
        <div className="sm-config-panel">
          <div className="sm-field">
            <label htmlFor="model-input">Model</label>
            <input
              id="model-input"
              type="text"
              list="known-models"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              placeholder="MiniMax-M3 or anthropic/claude-sonnet-4-20250514"
            />
            <datalist id="known-models">
              {KNOWN_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </div>
          <div className="sm-field">
            <label htmlFor="api-key-input">API Key</label>
            <div className="sm-key-row">
              <input
                id="api-key-input"
                type="password"
                placeholder="Enter to override env key"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
              />
              <span
                className={`sm-key-badge sm-key-badge--${keySource ?? "unset"}`}
              >
                {keyLabel}
              </span>
            </div>
          </div>
          <p className="sm-http-warning">
            ⚠️ API key transmitted over HTTP — development use only
          </p>
          {saveStatus === "err" && <p className="sm-error">{errMsg}</p>}
          <div className="sm-actions">
            <button className="sm-btn-primary" onClick={handleSave}>
              Save
            </button>
          </div>
          {config && (
            <div className="sm-rate-chip">
              Rate limit: {config.rate_limit_used} / {config.rate_limit_max}{" "}
              req/hr
            </div>
          )}
        </div>
      </section>

      <section className="sm-section">
        <h3>Test Prompt</h3>
        <div className="sm-test-panel">
          <label htmlFor="test-prompt">Test Prompt (max 500 chars)</label>
          <textarea
            id="test-prompt"
            defaultValue="Reply with the single word: pong"
            maxLength={500}
            rows={2}
          />
          <button
            className="sm-btn-secondary"
            onClick={handleRunTest}
            disabled={status === "running"}
          >
            {status === "running" ? "Running..." : "Run Test"}
          </button>
          {result && <ResultCard result={result} onClear={reset} />}
          {error && <p className="sm-error">{error.message}</p>}
        </div>
      </section>

      <section className="sm-section">
        <h3>Session Totals</h3>
        <div className="sm-totals-bar">
          <div className="sm-chip">
            <span className="sm-chip-label">Tokens In</span>
            <span className="sm-chip-value">{formatNum(totals.tokens_in)}</span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Tokens Out</span>
            <span className="sm-chip-value">
              {formatNum(totals.tokens_out)}
            </span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Tool Calls</span>
            <span className="sm-chip-value">
              {formatNum(totals.tool_calls)}
            </span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Runs</span>
            <span className="sm-chip-value">{totals.runs_count}</span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">avg tok/s</span>
            <span className="sm-chip-value">{avgTps.toFixed(2)}</span>
          </div>
        </div>
      </section>

      <section className="sm-section">
        <div className="sm-table-header">
          <h3>Per-Run Stats</h3>
          {runs.length > 0 && (
            <button className="sm-btn-ghost" onClick={clearStats}>
              Clear
            </button>
          )}
        </div>
        {runs.length === 0 ? (
          <p className="sm-empty">No runs this session yet.</p>
        ) : (
          <table className="sm-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Model</th>
                <th>In</th>
                <th>Out</th>
                <th title="For batch enrichment runs. Includes tool execution + DB writes. For pure LLM speed, use the Test Prompt panel above.">
                  avg tok/s
                </th>
                <th>Calls</th>
                <th>Duration</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={`${r.task_id}-${r.timestamp}`}>
                  <td>{r.task_id.slice(0, 8)}</td>
                  <td>
                    {r.model.includes("/") ? r.model.split("/")[1] : r.model}
                  </td>
                  <td>{formatNum(r.tokens_in)}</td>
                  <td>{formatNum(r.tokens_out)}</td>
                  <td>{r.tps}</td>
                  <td>{r.tool_calls}</td>
                  <td>{r.duration_s}s</td>
                  <td>{fmtTs(r.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
};

export default SystemMetrics;
