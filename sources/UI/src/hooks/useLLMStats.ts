import { useCallback, useEffect, useState } from "react";
import { wsService } from "../services/api";

const STORAGE_KEY = "kf_llm_stats";

export type LLMRun = {
  task_id: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  duration_s: number;
  tps: number;
  timestamp: string;
};

export type LLMTotals = {
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  runs_count: number;
};

function computeTotals(runs: LLMRun[]): LLMTotals {
  return runs.reduce(
    (acc, r) => ({
      tokens_in: acc.tokens_in + r.tokens_in,
      tokens_out: acc.tokens_out + r.tokens_out,
      tool_calls: acc.tool_calls + r.tool_calls,
      runs_count: acc.runs_count + 1,
    }),
    { tokens_in: 0, tokens_out: 0, tool_calls: 0, runs_count: 0 },
  );
}

function computeAvgTps(runs: LLMRun[]): number {
  if (!runs.length) return 0;
  const sum = runs.reduce((acc, r) => acc + r.tps, 0);
  return Math.round((sum / runs.length) * 100) / 100;
}

function loadFromStorage(): LLMRun[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as LLMRun[]) : [];
  } catch {
    return [];
  }
}

function saveToStorage(runs: LLMRun[]): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
}

export function useLLMStats() {
  const [runs, setRuns] = useState<LLMRun[]>(loadFromStorage);
  const [totals, setTotals] = useState<LLMTotals>(() => computeTotals(loadFromStorage()));

  const clearStats = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setRuns([]);
    setTotals({ tokens_in: 0, tokens_out: 0, tool_calls: 0, runs_count: 0 });
  }, []);

  const addRun = useCallback((run: Omit<LLMRun, "timestamp">) => {
    const full: LLMRun = { ...run, timestamp: new Date().toISOString() };
    setRuns((prev) => {
      const next = [...prev, full];
      saveToStorage(next);
      return next;
    });
    setTotals((prev) => ({
      tokens_in: prev.tokens_in + full.tokens_in,
      tokens_out: prev.tokens_out + full.tokens_out,
      tool_calls: prev.tool_calls + full.tool_calls,
      runs_count: prev.runs_count + 1,
    }));
  }, []);

  useEffect(() => {
    const listener = (msg: unknown) => {
      if (
        !msg ||
        typeof msg !== "object" ||
        !("event" in msg) ||
        (msg as { event: string }).event !== "enrichment_complete"
      ) {
        return;
      }
      const data = (msg as { data: Record<string, unknown> }).data;
      if (!data || typeof data.tokens_in !== "number") return;

      const task_id = (msg as { task_id: string }).task_id;
      const run: LLMRun = {
        task_id,
        model: String(data.model ?? ""),
        tokens_in: data.tokens_in as number,
        tokens_out: data.tokens_out as number,
        tool_calls: data.tool_calls_used as number,
        duration_s: data.duration_s as number,
        tps: data.duration_s > 0
          ? Math.round(((data.tokens_in as number) + (data.tokens_out as number)) / (data.duration_s as number))
          : 0,
        timestamp: new Date().toISOString(),
      };

      setRuns((prev) => {
        const next = [...prev, run];
        saveToStorage(next);
        return next;
      });
      setTotals((prev) => {
        const t = run;
        return {
          tokens_in: prev.tokens_in + t.tokens_in,
          tokens_out: prev.tokens_out + t.tokens_out,
          tool_calls: prev.tool_calls + t.tool_calls,
          runs_count: prev.runs_count + 1,
        };
      });
    };

    wsService.on("message", listener);
    return () => {
      wsService.off("message", listener);
    };
  }, []);

  const avgTps = computeAvgTps(runs);

  return { runs, totals, avgTps, clearStats, addRun };
}