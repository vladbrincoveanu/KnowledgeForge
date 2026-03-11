/* @vitest-environment jsdom */

import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import EdgeDetailsPanel from "./EdgeDetailsPanel";

expect.extend(matchers);

afterEach(() => {
  cleanup();
});

describe("EdgeDetailsPanel", () => {
  test("shows a friendly loading status without rendering a thinking bubble", () => {
    render(
      <EdgeDetailsPanel
        selectedEdge={{
          source: "OmniPay Platform",
          target: "GlobalBank",
          data: { description: "Uses GlobalBank for settlement." },
        }}
        onClose={vi.fn()}
        edgeDescription=""
        isEdgeLoading={false}
        chatMessages={[]}
        isChatLoading
        onSendChat={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("Preparing a response...")).toBeInTheDocument();
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });

  test("scrolls to the latest edge chat message", () => {
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    const props = {
      selectedEdge: {
        source: "OmniPay Platform",
        target: "GlobalBank",
        data: { description: "Uses GlobalBank for settlement." },
      },
      onClose: vi.fn(),
      edgeDescription: "",
      isEdgeLoading: false,
      isChatLoading: false,
      onSendChat: vi.fn().mockResolvedValue(undefined),
    };

    const { rerender } = render(
      <EdgeDetailsPanel {...props} chatMessages={[]} />,
    );

    scrollIntoView.mockClear();

    rerender(
      <EdgeDetailsPanel
        {...props}
        chatMessages={[
          { role: "assistant", content: "GlobalBank handles settlement." },
        ]}
      />,
    );

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "end" });

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: originalScrollIntoView,
    });
  });
});
