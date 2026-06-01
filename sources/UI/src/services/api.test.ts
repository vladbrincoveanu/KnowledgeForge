import { describe, it, expect, vi, beforeEach } from "vitest";
import { llmConfigAPI } from "./api";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(body, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("llmConfigAPI.testPrompt", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("yields parsed SSE events from chunked response", async () => {
    const frames = [
      'data: {"type":"meta","model":"MiniMax-M2.7","ttft_ms":100}\n\n',
      'data: {"type":"chunk","delta":"p"}\n\n',
      'data: {"type":"chunk","delta":"ong"}\n\n',
      'data: {"type":"done","total_ms":200,"tokens_in":3,"tokens_out":3,"tps":15}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(frames)));

    const out: unknown[] = [];
    for await (const ev of llmConfigAPI.testPrompt("ping")) {
      out.push(ev);
    }
    expect(out).toEqual([
      { type: "meta", model: "MiniMax-M2.7", ttft_ms: 100 },
      { type: "chunk", delta: "p" },
      { type: "chunk", delta: "ong" },
      { type: "done", total_ms: 200, tokens_in: 3, tokens_out: 3, tps: 15 },
    ]);
  });

  it("throws on non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "no key" }), { status: 401 }),
      ),
    );
    await expect(async () => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      for await (const _ of llmConfigAPI.testPrompt("hi")) {
        /* drain */
      }
    }).rejects.toThrow(/401/);
  });
});
