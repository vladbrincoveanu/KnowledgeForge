/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTestPrompt } from "./useTestPrompt";

function asyncIterFromArray<T>(arr: T[]): AsyncGenerator<T> {
  return (async function* () {
    for (const x of arr) yield x;
  })();
}

describe("useTestPrompt", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("starts in idle state", () => {
    const { result } = renderHook(() => useTestPrompt());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("transitions idle -> running -> ok on success", async () => {
    const events = [
      {
        type: "meta" as const,
        model: "MiniMax-M2.7",
        ttft_ms: 100,
        ts: "2026-06-01T10:00:00Z",
      },
      { type: "chunk" as const, delta: "p" },
      { type: "chunk" as const, delta: "ong" },
      {
        type: "done" as const,
        total_ms: 200,
        tokens_in: 3,
        tokens_out: 3,
        tps: 15,
      },
    ];
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(
      asyncIterFromArray(events),
    );

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => {
      await result.current.run("ping");
    });
    expect(result.current.status).toBe("ok");
    expect(result.current.result?.response).toBe("pong");
    expect(result.current.result?.tps).toBe(15);
    expect(result.current.result?.ttftMs).toBe(100);
    // Server-side timestamp from the meta event should be captured.
    expect(result.current.result?.timestamp).toBe("2026-06-01T10:00:00Z");
  });

  it("sets error on error event", async () => {
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(
      asyncIterFromArray([
        {
          type: "error" as const,
          code: "rate_limited",
          message: "nope",
        },
      ]),
    );

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => {
      await result.current.run("hi");
    });
    expect(result.current.status).toBe("err");
    expect(result.current.error?.code).toBe("rate_limited");
  });

  it("reset() clears result and error", async () => {
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(
      asyncIterFromArray([
        { type: "error" as const, code: "x", message: "x" },
      ]),
    );

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => {
      await result.current.run("hi");
    });
    act(() => result.current.reset());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
