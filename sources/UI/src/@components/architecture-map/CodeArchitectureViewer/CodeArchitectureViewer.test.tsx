/* @vitest-environment jsdom */

import React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
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
vi.mock("./components/GraphView", () => ({
  default: () => <div data-testid="graph-view">GraphView</div>,
}));
vi.mock("./components/NodeDetailsPanel", () => ({
  default: () => <div data-testid="node-details-panel">NodeDetailsPanel</div>,
}));
vi.mock("./components/EdgeDetailsPanel", () => ({
  default: () => <div data-testid="edge-details-panel">EdgeDetailsPanel</div>,
}));
vi.mock("dagre", () => ({
  default: { graphlib: { Graph: vi.fn() }, layout: vi.fn() },
}));

// Mock the API
const mockGetArchitecture = vi.fn();
vi.mock("../../../services/api", () => ({
  codeArchitectureAPI: {
    getArchitecture: (...args: any[]) => mockGetArchitecture(...args),
    extractFromGitHub: vi.fn(),
    getExtractionStatus: vi.fn(),
    getExtractionResults: vi.fn(),
    extractFromGitHubOrg: vi.fn(),
    describeEdge: vi.fn(),
    chatWithContext: vi.fn(),
    clearArchitecture: vi.fn(),
  },
}));

import CodeArchitectureViewer from "./CodeArchitectureViewer";

const emptyArchitecture = {
  c4_model_version: "1.0",
  system_context: { name: "TestSystem" },
  containers: [],
  context_level: { entities: [], relationships: [] },
};

describe("CodeArchitectureViewer", () => {
  afterEach(() => {
    vi.clearAllMocks();
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
