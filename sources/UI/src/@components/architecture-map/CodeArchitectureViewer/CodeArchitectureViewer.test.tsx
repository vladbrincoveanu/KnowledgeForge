/* @vitest-environment jsdom */

import React from "react";
import { act, render, screen, waitFor, cleanup } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { afterEach, describe, expect, test, vi } from "vitest";

expect.extend(matchers);

// Mock reactflow (complex canvas library) before importing the component
vi.mock("reactflow", async () => {
  const actual = await vi.importActual<typeof import("reactflow")>("reactflow");
  return {
    ...actual,
    ReactFlow: ({ children }: any) => (
      <div data-testid="react-flow">{children}</div>
    ),
    ReactFlowProvider: ({ children }: any) => <div>{children}</div>,
    useNodesState: () => [[], vi.fn(), vi.fn()],
    useEdgesState: () => [[], vi.fn(), vi.fn()],
    useReactFlow: () => ({
      fitView: vi.fn(),
      setNodes: vi.fn(),
      setEdges: vi.fn(),
    }),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    Position: actual.Position,
    MarkerType: actual.MarkerType,
  };
});

// Mock sub-components with correct default export format
vi.mock("./CustomNode", () => ({
  default: () => <div data-testid="custom-node" />,
}));
vi.mock("./ContainerNode", () => ({
  default: () => <div data-testid="container-node" />,
}));
vi.mock("./C4Edge", () => ({ default: () => null }));
vi.mock("./components/ArchitectureHeader", () => ({
  default: () => (
    <div data-testid="architecture-header">ArchitectureHeader</div>
  ),
}));
vi.mock("./components/MetricsBar", () => ({
  default: () => <div data-testid="metrics-bar">MetricsBar</div>,
}));
let capturedGraphViewProps: any = null;
vi.mock("./components/GraphView", () => ({
  default: (props: any) => {
    capturedGraphViewProps = props;
    return <div data-testid="graph-view">GraphView</div>;
  },
}));
let capturedNodeDetailsPanelProps: any = null;
vi.mock("./components/NodeDetailsPanel", () => ({
  default: (props: any) => {
    capturedNodeDetailsPanelProps = props;
    return <div data-testid="node-details-panel">NodeDetailsPanel</div>;
  },
}));
vi.mock("./components/EdgeDetailsPanel", () => ({
  default: () => <div data-testid="edge-details-panel">EdgeDetailsPanel</div>,
}));
vi.mock("dagre", () => ({
  default: { graphlib: { Graph: vi.fn() }, layout: vi.fn() },
}));

// Mock the API
const mockGetArchitecture = vi.fn();
const mockStreamChatWithContext = vi.fn();
vi.mock("../../../services/api", () => ({
  codeArchitectureAPI: {
    getArchitecture: (...args: any[]) => mockGetArchitecture(...args),
    extractFromGitHub: vi.fn(),
    getExtractionStatus: vi.fn(),
    getExtractionResults: vi.fn(),
    extractFromGitHubOrg: vi.fn(),
    describeEdge: vi.fn(),
    chatWithContext: vi.fn(),
    streamChatWithContext: (...args: any[]) =>
      mockStreamChatWithContext(...args),
    clearArchitecture: vi.fn(),
  },
}));

import CodeArchitectureViewer, { generateC4Edges } from "./CodeArchitectureViewer";

const emptyArchitecture = {
  c4_model_version: "1.0",
  system_context: { name: "TestSystem" },
  containers: [],
  context_level: { entities: [], relationships: [] },
};

describe("CodeArchitectureViewer", () => {
  afterEach(() => {
    vi.clearAllMocks();
    capturedGraphViewProps = null;
    capturedNodeDetailsPanelProps = null;
    cleanup();
  });

  test("renders without crashing", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
  });

  test("calls getArchitecture on mount", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalledTimes(1));
  });

  test("renders ArchitectureHeader sub-component", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    expect(screen.getByTestId("architecture-header")).toBeInTheDocument();
  });

  test("renders MetricsBar sub-component", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    expect(screen.getByTestId("metrics-bar")).toBeInTheDocument();
  });

  test("renders GraphView sub-component", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    expect(screen.getByTestId("graph-view")).toBeInTheDocument();
  });

  test("handles getArchitecture error without crashing", async () => {
    mockGetArchitecture.mockRejectedValueOnce(new Error("Network error"));
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    // On error, an error message or empty container should be rendered (not crash)
    const viewer = document.querySelector(".code-architecture-viewer");
    expect(viewer).not.toBeNull();
  });

  test("handles empty architecture without crashing", async () => {
    mockGetArchitecture.mockResolvedValueOnce({});
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    expect(screen.getByTestId("architecture-header")).toBeInTheDocument();
  });

  test("handles architecture with null context_level", async () => {
    mockGetArchitecture.mockResolvedValueOnce({
      c4_model_version: "1.0",
      context_level: null,
    });
    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
    expect(screen.getByTestId("graph-view")).toBeInTheDocument();
  });

  test("buffers streamed chat until the final assistant answer is ready", async () => {
    mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);

    let resolveStream: (() => void) | undefined;
    let pendingHandlers:
      | {
          onDelta: (delta: string) => void;
          onComplete?: (source: string) => void;
        }
      | undefined;

    mockStreamChatWithContext.mockImplementation(
      async (
        _payload: unknown,
        handlers: {
          onDelta: (delta: string) => void;
          onComplete?: (source: string) => void;
        },
      ) =>
        new Promise<void>((resolve) => {
          pendingHandlers = handlers;
          resolveStream = resolve;
        }),
    );

    render(<CodeArchitectureViewer />);
    await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());

    await act(async () => {
      capturedGraphViewProps.onNodeClick({} as React.MouseEvent, {
        data: {
          id: "globalbank",
          name: "GlobalBank",
          type: "external_system",
          attributes: {},
        },
      });
    });

    await waitFor(() =>
      expect(capturedNodeDetailsPanelProps.selectedNode?.name).toBe(
        "GlobalBank",
      ),
    );

    await act(async () => {
      void capturedNodeDetailsPanelProps.onSendChat("What does GlobalBank do?");
    });

    await waitFor(() =>
      expect(capturedNodeDetailsPanelProps.chatMessages).toEqual([
        { role: "user", content: "What does GlobalBank do?" },
      ]),
    );

    act(() => {
      pendingHandlers?.onDelta("GlobalBank ");
      pendingHandlers?.onDelta("handles settlement.");
    });

    expect(capturedNodeDetailsPanelProps.chatMessages).toEqual([
      { role: "user", content: "What does GlobalBank do?" },
    ]);

    await act(async () => {
      pendingHandlers?.onComplete?.("llm");
      resolveStream?.();
    });

    await waitFor(() =>
      expect(capturedNodeDetailsPanelProps.chatMessages).toEqual([
        { role: "user", content: "What does GlobalBank do?" },
        { role: "assistant", content: "GlobalBank handles settlement." },
      ]),
    );
  });

  // Smoke tests
  for (let i = 1; i <= 5; i++) {
    test(`render smoke test ${i}`, async () => {
      mockGetArchitecture.mockResolvedValueOnce(emptyArchitecture);
      render(<CodeArchitectureViewer />);
      await waitFor(() => expect(mockGetArchitecture).toHaveBeenCalled());
      expect(screen.getByTestId("architecture-header")).toBeInTheDocument();
      cleanup();
    });
  }
});

describe("generateC4Edges", () => {
  test("resolves helm name mismatch via prefix-strip fallback", () => {
    const containers = [
      { name: "omnipay-settlement-orchestrator", container_type: "Service" },
    ];
    const relationships = [
      { from: "settlement-orchestrator", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const { nodes, edges } = generateC4Edges(containers, relationships, []);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe("container_omnipay-settlement-orchestrator");
    expect(edges[0].target).toBe("ghost_external_kafka");
  });

  test("creates ghost external node when target is unresolved and not in context externals", () => {
    const containers = [
      { name: "omnipay-event-projections" },
    ];
    const relationships = [
      { from: "omnipay-event-projections", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const { nodes, edges } = generateC4Edges(containers, relationships, []);
    expect(edges).toHaveLength(1);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].id).toBe("ghost_external_kafka");
    expect(nodes[0].data.attributes.isGhostExternal).toBe(true);
  });

  test("links to context external node instead of creating ghost when target matches", () => {
    const containers = [
      { name: "omnipay-settlement-orchestrator" },
    ];
    const relationships = [
      { from: "omnipay-settlement-orchestrator", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const contextExternals = [
      { id: "context_external_0", name: "kafka", entity_type: "external_system" },
    ];
    const { nodes, edges } = generateC4Edges(containers, relationships, contextExternals);
    expect(edges).toHaveLength(1);
    expect(edges[0].target).toBe("context_external_0");
    expect(nodes).toHaveLength(0); // no ghost created
  });
});
