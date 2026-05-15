/* @vitest-environment jsdom */

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useEnrichmentWS } from "../useEnrichmentWS";

vi.mock("../../services/api", () => ({
  wsService: {
    on: vi.fn(),
    off: vi.fn(),
  },
}));

describe("useEnrichmentWS", () => {
  it("accumulates node_added events", () => {
    const { result } = renderHook(() => useEnrichmentWS("t1"));
    act(() => {
      result.current._inject({
        event: "node_added",
        task_id: "t1",
        data: {
          name: "Stripe",
          canonical_name: "stripe",
          decision_mode: "LLM_ADJUDICATED",
        },
      });
    });
    expect(result.current.enrichedNodes).toHaveLength(1);
    expect(result.current.enrichedNodes[0].name).toBe("Stripe");
  });

  it("sets partial flag on enrichment_complete", () => {
    const { result } = renderHook(() => useEnrichmentWS("t1"));
    act(() => {
      result.current._inject({
        event: "enrichment_complete",
        task_id: "t1",
        data: { partial: true, reason: "budget", nodes_added: 3 },
      });
    });
    expect(result.current.partial).toBe(true);
    expect(result.current.partialReason).toBe("budget");
  });
});
