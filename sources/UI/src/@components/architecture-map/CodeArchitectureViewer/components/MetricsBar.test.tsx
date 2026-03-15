/* @vitest-environment jsdom */

import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import MetricsBar from "./MetricsBar";

expect.extend(matchers);

const baseProps = {
  searchTerm: "",
  setSearchTerm: vi.fn(),
  selectedLevel: "context_level",
  toggleLevel: vi.fn(),
  relationshipTypes: [],
  selectedRelationshipTypes: [],
  toggleRelationshipType: vi.fn(),
  showExternal: true,
  setShowExternal: vi.fn(),
  dependencyViewFilter: "all" as const,
  setDependencyViewFilter: vi.fn(),
  repoSectionExpanded: false,
  setRepoSectionExpanded: vi.fn(),
  githubUrl: "",
  setGithubUrl: vi.fn(),
  localPath: "",
  setLocalPath: vi.fn(),
  isExtracting: false,
  handleExtractFromGithub: vi.fn(),
  handleScanLocalPath: vi.fn(),
  handleBatchExtract: vi.fn(),
  handleGitHubOrgScan: vi.fn(),
  setArchitecture: vi.fn(),
  setNodes: vi.fn(),
  setEdges: vi.fn(),
  setExtractionStatus: vi.fn(),
  setExtractionError: vi.fn(),
  extractionStatus: null,
  extractionError: null,
};

describe("MetricsBar", () => {
  test("renders without errors", () => {
    const { container } = render(<MetricsBar {...baseProps} />);

    expect(container.querySelector(".metrics-bar")).toBeInTheDocument();
  });

  test("does not render Add Repository button", () => {
    const { container } = render(<MetricsBar {...baseProps} />);

    expect(container.querySelector(".extract-btn")).not.toBeInTheDocument();
    expect(container.querySelector(".repo-panel")).not.toBeInTheDocument();
  });
});
