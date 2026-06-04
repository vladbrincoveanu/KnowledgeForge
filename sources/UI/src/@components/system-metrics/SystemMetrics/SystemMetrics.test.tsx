/* @vitest-environment jsdom */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SystemMetrics from "./SystemMetrics";

// Mock the hook to drive state directly
const mockRun = vi.fn();
const mockReset = vi.fn();
vi.mock("../../../hooks/useTestPrompt", () => ({
  useTestPrompt: () => ({
    status: "idle" as const,
    result: null,
    error: null,
    run: mockRun,
    reset: mockReset,
  }),
}));

describe("SystemMetrics test panel", () => {
  beforeEach(() => {
    mockRun.mockReset();
  });

  it("renders free-text model input with datalist", async () => {
    render(<SystemMetrics />);
    // wait for initial config load
    const modelInput = await screen.findByPlaceholderText(
      /MiniMax-M2.7|anthropic/,
    );
    expect(modelInput.tagName).toBe("INPUT");
    expect(modelInput.getAttribute("list")).toBe("known-models");
  });

  it("renders prompt textarea with default 'Reply with: pong'", async () => {
    render(<SystemMetrics />);
    const ta = await screen.findByLabelText(/test prompt/i);
    expect((ta as HTMLTextAreaElement).value).toBe(
      "Reply with the single word: pong",
    );
  });

  it("calls run on Run button click", async () => {
    render(<SystemMetrics />);
    const runBtn = await screen.findByRole("button", { name: /run test/i });
    fireEvent.click(runBtn);
    expect(mockRun).toHaveBeenCalled();
  });
});
