/* @vitest-environment jsdom */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

expect.extend(matchers);

vi.mock("@/services/api", () => ({
  codeArchitectureAPI: {
    extractFromGitHub: vi.fn(),
    getExtractionStatus: vi.fn(),
  },
  wsService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  },
}));

import FileUploader from "./FileUploader";
import { RepoProvider, useRepos } from "../RepoProvider/RepoProvider";

const REPO_A = "https://github.com/facebook/react";

const Harness: React.FC<{
  onReady?: (api: ReturnType<typeof useRepos>) => void;
}> = ({ onReady }) => {
  const api = useRepos();
  React.useEffect(() => {
    onReady?.(api);
  }, [api, onReady]);
  return null;
};

const renderWithProvider = () => {
  let api!: ReturnType<typeof useRepos>;
  render(
    <RepoProvider>
      <FileUploader
        isProcessing={false}
        onExtractionStarted={vi.fn()}
        showNotification={vi.fn()}
      />
      <Harness
        onReady={(a) => {
          api = a;
        }}
      />
    </RepoProvider>,
  );
  return { getApi: () => api };
};

describe("FileUploader (refactored — input only)", () => {
  const mockShowNotification = vi.fn();
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("renders GitHub URL input by default", () => {
    render(
      <RepoProvider>
        <FileUploader
          isProcessing={false}
          onExtractionStarted={vi.fn()}
          showNotification={mockShowNotification}
        />
      </RepoProvider>,
    );
    expect(
      screen.getByPlaceholderText(/github\.com\/owner\/repo/i),
    ).toBeInTheDocument();
  });

  it("Add button calls addRepo via context and clears inputs", () => {
    const { getApi } = renderWithProvider();
    const input = screen.getByPlaceholderText(/github\.com\/owner\/repo/i);
    fireEvent.change(input, { target: { value: REPO_A } });
    fireEvent.click(screen.getByRole("button", { name: /^Add$/i }));
    expect(getApi().repos).toHaveLength(1);
    expect(getApi().repos[0].url).toBe(REPO_A);
  });

  it("Add with invalid URL shows notification and does not add", () => {
    const { getApi } = renderWithProvider();
    const input = screen.getByPlaceholderText(/github\.com\/owner\/repo/i);
    fireEvent.change(input, { target: { value: "garbage" } });
    fireEvent.click(screen.getByRole("button", { name: /^Add$/i }));
    expect(getApi().repos).toHaveLength(0);
  });

  it("switches to Local Folder tab", () => {
    render(
      <RepoProvider>
        <FileUploader
          isProcessing={false}
          onExtractionStarted={vi.fn()}
          showNotification={mockShowNotification}
        />
      </RepoProvider>,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Local Folder/i }));
    expect(screen.getByRole("tab", { name: /Local Folder/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("Enter key in URL input triggers Add", () => {
    const { getApi } = renderWithProvider();
    const input = screen.getByPlaceholderText(/github\.com\/owner\/repo/i);
    fireEvent.change(input, { target: { value: REPO_A } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(getApi().repos).toHaveLength(1);
  });
});
