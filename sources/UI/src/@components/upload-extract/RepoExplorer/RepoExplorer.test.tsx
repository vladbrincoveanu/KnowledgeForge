/* @vitest-environment jsdom */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";

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

import { codeArchitectureAPI } from "@/services/api";
import { RepoProvider, useRepos } from "../RepoProvider/RepoProvider";
import RepoExplorer from "./RepoExplorer";

const REPO_A = "https://github.com/facebook/react";
const REPO_B = "https://github.com/microsoft/typescript";

interface HarnessProps {
  onReady?: (api: ReturnType<typeof useRepos>) => void;
  onExtractionStarted?: (taskId: string, file: unknown) => void;
}

const Harness: React.FC<HarnessProps> = ({ onReady, onExtractionStarted }) => {
  const api = useRepos();
  React.useEffect(() => {
    onReady?.(api);
  }, [api, onReady]);
  return <RepoExplorer onExtractionStarted={onExtractionStarted} />;
};

const renderExplorer = (
  overrides: {
    onExtractionStarted?: (taskId: string, file: unknown) => void;
  } = {},
) => {
  let api!: ReturnType<typeof useRepos>;
  const onExtractionStarted = overrides.onExtractionStarted ?? vi.fn();
  render(
    <RepoProvider>
      <Harness
        onReady={(a) => {
          api = a;
        }}
        onExtractionStarted={onExtractionStarted}
      />
    </RepoProvider>,
  );
  return { getApi: () => api, onExtractionStarted };
};

describe("RepoExplorer", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("renders empty state when no repos", () => {
    renderExplorer();
    expect(
      screen.getByText(/Add one or more repository URLs above/i),
    ).toBeInTheDocument();
  });

  it("renders a row per repo with URL and status", () => {
    const { getApi } = renderExplorer();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    expect(screen.getByText(REPO_A)).toBeInTheDocument();
    expect(screen.getByText(REPO_B)).toBeInTheDocument();
    const readyBadges = screen.getAllByText(/Ready/i);
    expect(readyBadges.length).toBeGreaterThanOrEqual(2);
  });

  it("Remove button calls removeRepo", () => {
    const { getApi } = renderExplorer();
    act(() => getApi().addRepo(REPO_A));
    const removeBtn = screen.getByTitle("Remove");
    act(() => fireEvent.click(removeBtn));
    expect(getApi().repos).toHaveLength(0);
  });

  it("Extract All button calls startExtraction for each idle repo", async () => {
    (codeArchitectureAPI.extractFromGitHub as any).mockResolvedValue({
      task_id: "task-1",
    });
    const { getApi, onExtractionStarted } = renderExplorer();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    const extractBtn = screen.getByRole("button", { name: /Extract 2 Repos/i });
    await act(async () => {
      fireEvent.click(extractBtn);
    });
    expect(codeArchitectureAPI.extractFromGitHub).toHaveBeenCalledTimes(2);
    expect(onExtractionStarted).toHaveBeenCalled();
  });

  it("Append toggle changes startExtraction append param", async () => {
    (codeArchitectureAPI.extractFromGitHub as any).mockResolvedValue({
      task_id: "task-1",
    });
    const { getApi } = renderExplorer();
    act(() => {
      getApi().addRepo(REPO_A);
    });
    const extractBtn = screen.getByRole("button", { name: /Extract 1 Repo/i });
    await act(async () => {
      fireEvent.click(extractBtn);
    });
    expect(codeArchitectureAPI.extractFromGitHub).toHaveBeenLastCalledWith(
      REPO_A,
      true,
      false,
      undefined,
    );
    const toggle = screen.getByLabelText(/Add to existing graph data/i);
    fireEvent.click(toggle);
    act(() => {
      getApi().addRepo(REPO_B);
    });
    await act(async () => {
      fireEvent.click(extractBtn);
    });
    expect(codeArchitectureAPI.extractFromGitHub).toHaveBeenLastCalledWith(
      REPO_B,
      true,
      true,
      undefined,
    );
  });

  it("Clear All button calls clearAll", () => {
    const { getApi } = renderExplorer();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    const clearBtn = screen.getByRole("button", { name: /Clear All/i });
    act(() => fireEvent.click(clearBtn));
    expect(getApi().repos).toEqual([]);
  });

  describe("URL drag-drop", () => {
    function dropText(text: string) {
      const explorer = document.querySelector(".repo-explorer");
      expect(explorer).not.toBeNull();
      const dataTransfer = {
        types: ["text/plain"],
        getData: (type: string) => (type === "text/plain" ? text : ""),
        dropEffect: "",
      } as unknown as DataTransfer;
      const event = new Event("drop", { bubbles: true, cancelable: true });
      Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
      fireEvent(explorer!, event);
    }

    it("adds a single dropped GitHub URL to the queue", () => {
      const { getApi } = renderExplorer();
      act(() => {
        dropText("https://github.com/facebook/react");
      });
      expect(getApi().repos).toHaveLength(1);
      expect(getApi().repos[0].url).toBe("https://github.com/facebook/react");
    });

    it("extracts the first valid URL from mixed text", () => {
      const { getApi } = renderExplorer();
      act(() => {
        dropText("check this out https://github.com/vercel/next.js and more");
      });
      expect(getApi().repos).toHaveLength(1);
      expect(getApi().repos[0].url).toBe("https://github.com/vercel/next.js");
    });

    it("ignores non-URL text without adding anything", () => {
      const { getApi } = renderExplorer();
      act(() => {
        dropText("just some plain text, no links here");
      });
      expect(getApi().repos).toEqual([]);
    });

    it("ignores non-http(s) schemes", () => {
      const { getApi } = renderExplorer();
      act(() => {
        dropText("ftp://example.com/repo git://host/repo file:///tmp/x");
      });
      expect(getApi().repos).toEqual([]);
    });
  });
});
