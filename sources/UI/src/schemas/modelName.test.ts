import { describe, it, expect } from "vitest";
import { isValidModelName } from "./modelName";

describe("isValidModelName", () => {
  it("accepts anthropic format", () => {
    expect(isValidModelName("anthropic/claude-sonnet-4-20250514")).toBe(true);
  });
  it("accepts anthropic with dots and dashes", () => {
    expect(isValidModelName("anthropic/claude-3.5-sonnet-v2")).toBe(true);
  });
  it("accepts MiniMax format", () => {
    expect(isValidModelName("MiniMax-M2.7")).toBe(true);
  });
  it.each([
    ["gpt-4"],
    ["claude"],
    [""],
    ["anthropic/"],
    ["MiniMax"],
    ["openai/gpt-4"],
    ["random-string"],
  ])("rejects %s", (bad) => {
    expect(isValidModelName(bad)).toBe(false);
  });
});
