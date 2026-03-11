/* @vitest-environment jsdom */

import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import NodeDetailsPanel from "./NodeDetailsPanel";

expect.extend(matchers);

afterEach(() => {
  cleanup();
});

describe("NodeDetailsPanel", () => {
  test("renders container ownership and risk metadata from containerMeta", () => {
    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "container",
          name: "omnipay-gateway",
          attributes: {},
          containerMeta: {
            owner: "Vlad",
            tier: "Tier 2 - Production Standard",
            data_class: "General",
            active_experts: 2,
            compliance: "COMPLIANT",
            compliance_confidence: 0.94,
            description: "Client API gateway for the mobile apps.",
          },
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={vi.fn().mockResolvedValue(undefined)}
        onApplyReviewDecision={vi.fn()}
      />,
    );

    expect(screen.getByText("Vlad")).toBeInTheDocument();
    expect(
      screen.getByText("Tier 2 - Production Standard"),
    ).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
    expect(screen.getByText("2 active experts")).toBeInTheDocument();
    expect(screen.getByText("Compliant")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();
  });

  test("renders human review controls for ambiguous external dependencies", () => {
    const onApplyReviewDecision = vi.fn();
    const onSendChat = vi.fn().mockResolvedValue(undefined);

    render(
      <NodeDetailsPanel
        selectedNode={{
          id: "context_external_7",
          type: "external_system",
          name: "SignalForge",
          attributes: {
            detected_from: "omnipay-gateway/README.md",
            dependency_type: "BUSINESS_SYSTEM",
            classification_confidence: 0.64,
            classification_reasoning:
              "The documentation is exploratory and still ambiguous.",
            decision_mode: "llm_adjudicated",
            review_status: "needs_review",
            requires_human_review: true,
            review_threshold: 0.7,
            review_options: [
              {
                id: "signalforge-business",
                label: "Keep At Context Level",
                value: "BUSINESS_SYSTEM",
                description:
                  "Treat SignalForge as an external risk-decisioning company.",
              },
              {
                id: "signalforge-technical",
                label: "Move To Container Level",
                value: "TECHNICAL_INFRA",
                description:
                  "Treat SignalForge as a technical integration detail.",
              },
            ],
            suggested_prompts: [
              "We use SignalForge for merchant risk scoring. Compare it with Sift and Sardine.",
            ],
            provider_alternatives: [
              {
                provider: "Sift",
                price_tier: "High",
                performance_tier: "Enterprise",
                profile: "Mature fraud network effects.",
              },
            ],
          },
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={onSendChat}
        onApplyReviewDecision={onApplyReviewDecision}
      />,
    );

    expect(screen.getByText("Needs Human Review")).toBeInTheDocument();
    expect(screen.getByText("External Dependency")).toBeInTheDocument();
    expect(
      screen.getByText(
        "I am not fully confident where SignalForge belongs in the context diagram.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Possible alternatives for SignalForge"),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /keep at context level/i }),
    );

    expect(onApplyReviewDecision).toHaveBeenCalledWith(
      expect.objectContaining({
        nodeId: "context_external_7",
        value: "BUSINESS_SYSTEM",
        label: "Keep At Context Level",
      }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /We use SignalForge for merchant risk scoring/i,
      }),
    );

    expect(onSendChat).toHaveBeenCalledWith(
      "We use SignalForge for merchant risk scoring. Compare it with Sift and Sardine.",
    );
  });

  test("clears the chat input immediately after sending", () => {
    let resolveSend: (() => void) | undefined;
    const onSendChat = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSend = resolve;
        }),
    );

    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "external_system",
          name: "GlobalBank",
          attributes: {},
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={onSendChat}
        onApplyReviewDecision={vi.fn()}
      />,
    );

    const textarea = screen.getByPlaceholderText("Ask about this node...");
    fireEvent.change(textarea, {
      target: { value: "Should this stay at context level?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send chat message" }),
    );

    expect(onSendChat).toHaveBeenCalledWith(
      "Should this stay at context level?",
    );
    expect(textarea).toHaveValue("");

    resolveSend?.();
  });

  test("scrolls to the latest chat message when new messages arrive", () => {
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    const props = {
      selectedNode: {
        type: "external_system",
        name: "GlobalBank",
        attributes: {},
      },
      onClose: vi.fn(),
      nodeDescription: "",
      isNodeLoading: false,
      isChatLoading: false,
      onSendChat: vi.fn().mockResolvedValue(undefined),
      onApplyReviewDecision: vi.fn(),
    };

    const { rerender } = render(
      <NodeDetailsPanel {...props} chatMessages={[]} />,
    );

    scrollIntoView.mockClear();

    rerender(
      <NodeDetailsPanel
        {...props}
        chatMessages={[{ role: "user", content: "What does GlobalBank do?" }]}
      />,
    );

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "end" });

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: originalScrollIntoView,
    });
  });

  test("shows a friendly status near the composer while preparing a response", () => {
    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "external_system",
          name: "GlobalBank",
          attributes: {},
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading
        onSendChat={vi.fn().mockResolvedValue(undefined)}
        onApplyReviewDecision={vi.fn()}
      />,
    );

    expect(screen.getByText("Preparing a response...")).toBeInTheDocument();
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });
});
