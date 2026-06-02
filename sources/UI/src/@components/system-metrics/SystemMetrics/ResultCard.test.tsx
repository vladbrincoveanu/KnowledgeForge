/* @vitest-environment jsdom */

import { describe, it, expect, vi, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ResultCard } from "./ResultCard";
import type { TestResult } from "../../../hooks/useTestPrompt";

expect.extend(matchers);
afterEach(cleanup);

const sample: TestResult = {
  model: "MiniMax-M2.7",
  prompt: "Reply with: pong",
  response: "pong",
  ttftMs: 342,
  totalMs: 1247,
  tokensIn: 8,
  tokensOut: 3,
  tps: 2.4,
  timestamp: "2026-06-01T10:00:00.000Z",
};

describe("ResultCard", () => {
  it("renders all stats", () => {
    render(<ResultCard result={sample} onClear={() => {}} />);
    expect(screen.getByText(/342/)).toBeTruthy(); // TTFT
    expect(screen.getByText(/1,?247/)).toBeTruthy(); // total
    expect(screen.getByText(/^8$/)).toBeTruthy(); // tokens in
    expect(screen.getByText(/^3$/)).toBeTruthy(); // tokens out
    expect(screen.getByText(/2\.4/)).toBeTruthy(); // tps
  });

  it("renders the response text in a pre block", () => {
    render(<ResultCard result={sample} onClear={() => {}} />);
    const pre = screen.getByText("pong");
    expect(pre.tagName).toBe("PRE");
  });

  it("calls onClear when Clear clicked", () => {
    const onClear = vi.fn();
    render(<ResultCard result={sample} onClear={onClear} />);
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(onClear).toHaveBeenCalled();
  });
});
