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
      />,
    );

    const textarea = screen.getByPlaceholderText("Ask about this node...");
    fireEvent.change(textarea, {
      target: { value: "Should this stay at context level?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send chat message" }));

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
      />,
    );

    expect(screen.getByText("Preparing a response...")).toBeInTheDocument();
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });

  test("container panel shows technology and protocol but not system fields", () => {
    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "container",
          name: "Streaming API",
          attributes: {
            description: "WebSocket service",
            technology: "Node.js",
            container_type: "service",
            protocol: "WebSocket",
            connections: { outgoing: [], incoming: [] },
            componentsInside: [],
            // Inherited from system — should NOT be shown on container panel
            owner: "Mastodon gGmbH",
            status: "ACTIVE",
            tier: "Tier 1",
            data_class: "PII",
            compliance: "MEDIUM_RISK",
          },
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("Node.js")).toBeInTheDocument();
    expect(screen.getByText("WebSocket")).toBeInTheDocument();
    expect(screen.getByText("service")).toBeInTheDocument();
    expect(screen.queryByText("Mastodon gGmbH")).not.toBeInTheDocument();
    expect(screen.queryByText("Tier 1")).not.toBeInTheDocument();
    expect(screen.queryByText("PII")).not.toBeInTheDocument();
  });

  test("container panel renders Connections list when relationships exist", () => {
    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "container",
          name: "Rails Web Application",
          attributes: {
            description: "Mastodon web app",
            technology: "Ruby on Rails",
            container_type: "service",
            connections: {
              outgoing: [
                { name: "PostgreSQL", protocol: "TCP", description: "Stores accounts" },
                { name: "Redis", protocol: "TCP", description: "Caches sessions" },
              ],
              incoming: [],
            },
            componentsInside: ["AccountsController", "StatusesController"],
          },
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("Connections")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("Redis")).toBeInTheDocument();
    expect(screen.getByText("Components Inside")).toBeInTheDocument();
  });

  test("component panel shows component_type and endpoint but not system fields", () => {
    render(
      <NodeDetailsPanel
        selectedNode={{
          type: "component",
          name: "AccountsController",
          attributes: {
            description: "Handles account REST endpoints",
            component_type: "http_handler",
            endpoint_method: "GET",
            endpoint_path: "/api/v1/accounts/:id",
            language: "Ruby",
            container: "Rails Web Application",
            connections: { outgoing: [], incoming: [] },
            // Inherited from system — should NOT be shown
            owner: "Mastodon gGmbH",
            tier: "Tier 1",
          },
        }}
        onClose={vi.fn()}
        nodeDescription=""
        isNodeLoading={false}
        chatMessages={[]}
        isChatLoading={false}
        onSendChat={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("http_handler")).toBeInTheDocument();
    expect(screen.getByText("GET /api/v1/accounts/:id")).toBeInTheDocument();
    expect(screen.getByText("Ruby")).toBeInTheDocument();
    expect(screen.getByText("Rails Web Application")).toBeInTheDocument();
    expect(screen.queryByText("Mastodon gGmbH")).not.toBeInTheDocument();
    expect(screen.queryByText("Tier 1")).not.toBeInTheDocument();
  });
});
