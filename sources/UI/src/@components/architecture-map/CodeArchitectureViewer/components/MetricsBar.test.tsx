/* @vitest-environment jsdom */

import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { fireEvent, render, screen } from "@testing-library/react";
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
  test("uses parent-controlled repo panel state when opening", () => {
    const setRepoSectionExpanded = vi.fn();

    render(
      <MetricsBar
        {...baseProps}
        repoSectionExpanded={false}
        setRepoSectionExpanded={setRepoSectionExpanded}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /add repository/i }));

    expect(setRepoSectionExpanded).toHaveBeenCalledWith(true);
  });

  test("uses parent-controlled repo panel state when closing", () => {
    const setRepoSectionExpanded = vi.fn();

    render(
      <MetricsBar
        {...baseProps}
        repoSectionExpanded
        setRepoSectionExpanded={setRepoSectionExpanded}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "×" }));

    expect(setRepoSectionExpanded).toHaveBeenCalledWith(false);
  });
});
