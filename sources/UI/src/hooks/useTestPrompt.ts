import { useCallback, useState } from "react";
import { llmConfigAPI, TestEvent } from "../services/api";
import { isValidModelName } from "../schemas/modelName";

export type TestStatus = "idle" | "running" | "ok" | "err";

export interface TestResult {
  model: string;
  prompt: string;
  response: string;
  ttftMs: number;
  totalMs: number;
  tokensIn: number;
  tokensOut: number;
  tps: number;
  timestamp: string;
}

export interface TestError {
  code: string;
  message: string;
}

export interface UseTestPromptReturn {
  status: TestStatus;
  result: TestResult | null;
  error: TestError | null;
  run: (prompt: string, model?: string) => Promise<void>;
  reset: () => void;
}

export function useTestPrompt(): UseTestPromptReturn {
  const [status, setStatus] = useState<TestStatus>("idle");
  const [result, setResult] = useState<TestResult | null>(null);
  const [error, setError] = useState<TestError | null>(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
  }, []);

  const run = useCallback(async (prompt: string, model?: string) => {
    setStatus("running");
    setError(null);

    if (!prompt || prompt.length < 1 || prompt.length > 500) {
      setError({
        code: "invalid_prompt",
        message: "Prompt must be 1-500 characters",
      });
      setStatus("err");
      return;
    }
    if (model && !isValidModelName(model)) {
      setError({ code: "invalid_model", message: "Invalid model format" });
      setStatus("err");
      return;
    }

    // Seed `timestamp` client-side; the first `meta` event from the server
    // will overwrite it with the authoritative server-side timestamp.
    const acc: Partial<TestResult> = {
      model: model ?? "",
      prompt,
      response: "",
      ttftMs: 0,
      totalMs: 0,
      tokensIn: 0,
      tokensOut: 0,
      tps: 0,
      timestamp: new Date().toISOString(),
    };
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 18_000);
    let gotDone = false;

    try {
      for await (const ev of llmConfigAPI.testPrompt(
        prompt,
        model,
        controller.signal,
      )) {
        // Surface SSE error events as TestError so the original `code` is
        // preserved (rather than reclassifying as a generic "network" error).
        if (ev.type === "error") {
          setError({ code: ev.code, message: ev.message });
          setStatus("err");
          return;
        }
        if (ev.type === "done") {
          gotDone = true;
        }
        handleEvent(ev as TestEvent, acc);
      }
      if (gotDone) {
        setResult(acc as TestResult);
        setStatus("ok");
      } else if (!acc.response) {
        setError({ code: "empty_response", message: "No response received" });
        setStatus("err");
      } else {
        setError({
          code: "stream_truncated",
          message: "Stream ended without completion",
        });
        setStatus("err");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (controller.signal.aborted) {
        setError({ code: "timeout", message: "No response in 18s" });
      } else {
        setError({ code: "network", message: msg });
      }
      setStatus("err");
    } finally {
      clearTimeout(timeoutId);
    }
  }, []);

  return { status, result, error, run, reset };
}

function handleEvent(ev: TestEvent, acc: Partial<TestResult>): void {
  switch (ev.type) {
    case "meta":
      acc.model = ev.model;
      acc.ttftMs = ev.ttft_ms;
      // Server-authoritative timestamp; overrides the client-side seed.
      acc.timestamp = ev.ts;
      return;
    case "chunk":
      acc.response = (acc.response ?? "") + ev.delta;
      return;
    case "done":
      acc.totalMs = ev.total_ms;
      acc.tokensIn = ev.tokens_in;
      acc.tokensOut = ev.tokens_out;
      acc.tps = ev.tps;
      return;
    case "error":
      // Handled directly in `run` so the original `code` is surfaced to the UI.
      return;
  }
}
