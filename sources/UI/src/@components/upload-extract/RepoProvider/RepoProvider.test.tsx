/* @vitest-environment jsdom */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, cleanup, act } from "@testing-library/react";
import { RepoProvider, useRepos, RepoEntry } from "./RepoProvider";
import { codeArchitectureAPI, wsService } from "@/services/api";

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

const TestConsumer: React.FC<{ onReady: (api: ReturnType<typeof useRepos>) => void }> = ({
  onReady,
}) => {
  const api = useRepos();
  React.useEffect(() => {
    onReady(api);
  }, [api, onReady]);
  return null;
};

const REPO_A = "https://github.com/facebook/react";
const REPO_B = "https://github.com/microsoft/typescript";

const renderWithProvider = () => {
  let api!: ReturnType<typeof useRepos>;
  render(
    <RepoProvider>
      <TestConsumer onReady={(a) => (api = a)} />
    </RepoProvider>,
  );
  return { getApi: () => api };
};

describe("RepoProvider — addRepo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => cleanup());

  it("appends a new repo with status=idle on valid URL", () => {
    const { getApi } = renderWithProvider();
    let result: ReturnType<ReturnType<typeof useRepos>["addRepo"]> = { ok: false, error: "" };
    act(() => {
      result = getApi().addRepo(REPO_A);
    });
    expect(result).toEqual({ ok: true });
    expect(getApi().repos).toHaveLength(1);
    expect(getApi().repos[0]).toMatchObject({
      url: REPO_A,
      status: "idle",
      message: "Ready to extract",
      progress: 0,
      containersCount: 0,
      componentsCount: 0,
    });
  });

  it("strips trailing .git and slash from URL", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo("https://github.com/facebook/react.git/");
    });
    expect(getApi().repos[0].url).toBe(REPO_A);
  });

  it("includes token when provided", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo(REPO_A, "ghp_xxx");
    });
    expect(getApi().repos[0].token).toBe("ghp_xxx");
  });

  it("omits token when empty string", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo(REPO_A, "  ");
    });
    expect(getApi().repos[0].token).toBeUndefined();
  });

  it("rejects empty URL", () => {
    const { getApi } = renderWithProvider();
    const result = getApi().addRepo("   ");
    expect(result).toEqual({ ok: false, error: "Please enter a repository URL." });
    expect(getApi().repos).toHaveLength(0);
  });

  it("rejects invalid URL", () => {
    const { getApi } = renderWithProvider();
    const result = getApi().addRepo("not a url");
    expect(result).toMatchObject({ ok: false });
    expect(getApi().repos).toHaveLength(0);
  });

  it("rejects duplicate URL", () => {
    const { getApi } = renderWithProvider();
    act(() => getApi().addRepo(REPO_A));
    const result = getApi().addRepo(REPO_A);
    expect(result).toEqual({ ok: false, error: "This repository has already been added." });
    expect(getApi().repos).toHaveLength(1);
  });

  it("accepts gitlab URL with /group/subgroup/repo", () => {
    const { getApi } = renderWithProvider();
    const result = getApi().addRepo("https://gitlab.tuwien.ac.at/ai/monorepo");
    expect(result).toEqual({ ok: true });
  });

  it("supports multiple repos", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    expect(getApi().repos.map((r) => r.url)).toEqual([REPO_A, REPO_B]);
  });
});

describe("RepoProvider — removeRepo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => cleanup());

  it("removes a repo by URL", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    act(() => getApi().removeRepo(REPO_A));
    expect(getApi().repos.map((r) => r.url)).toEqual([REPO_B]);
  });

  it("is a no-op for unknown URL", () => {
    const { getApi } = renderWithProvider();
    act(() => getApi().addRepo(REPO_A));
    act(() => getApi().removeRepo("https://github.com/other/repo"));
    expect(getApi().repos).toHaveLength(1);
  });
});

describe("RepoProvider — clearAll", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => cleanup());

  it("empties the repos list", () => {
    const { getApi } = renderWithProvider();
    act(() => {
      getApi().addRepo(REPO_A);
      getApi().addRepo(REPO_B);
    });
    act(() => getApi().clearAll());
    expect(getApi().repos).toEqual([]);
  });
});

describe("RepoProvider — startExtraction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => cleanup());

  it("calls extractFromGitHub, updates repo to pending with taskId, returns taskId", async () => {
    (codeArchitectureAPI.extractFromGitHub as any).mockResolvedValue({ task_id: "task-123" });
    const { getApi } = renderWithProvider();
    act(() => getApi().addRepo(REPO_A));
    let returned: string | null = "sentinel";
    await act(async () => {
      returned = await getApi().startExtraction(REPO_A, true);
    });
    expect(codeArchitectureAPI.extractFromGitHub).toHaveBeenCalledWith(REPO_A, true, true, undefined);
    expect(returned).toBe("task-123");
    const repo = getApi().repos[0];
    expect(repo.taskId).toBe("task-123");
    expect(repo.status).toBe("pending");
  });

  it("marks repo as failed when API throws, returns null", async () => {
    (codeArchitectureAPI.extractFromGitHub as any).mockRejectedValue({
      response: { data: { detail: "Bad URL" } },
    });
    const { getApi } = renderWithProvider();
    act(() => getApi().addRepo(REPO_A));
    let returned: string | null = "sentinel";
    await act(async () => {
      returned = await getApi().startExtraction(REPO_A, true);
    });
    expect(returned).toBeNull();
    const repo = getApi().repos[0];
    expect(repo.status).toBe("failed");
    expect(repo.message).toBe("Bad URL");
  });

  it("returns null when called for unknown url", async () => {
    const { getApi } = renderWithProvider();
    let returned: string | null = "sentinel";
    await act(async () => {
      returned = await getApi().startExtraction("https://unknown/x", true);
    });
    expect(returned).toBeNull();
  });

  it("updates repo from WS message matching taskId", async () => {
    (codeArchitectureAPI.extractFromGitHub as any).mockResolvedValue({ task_id: "task-123" });
    let capturedHandler: ((data?: unknown) => void) | undefined;
    (wsService.on as any).mockImplementation((event: string, cb: (data?: unknown) => void) => {
      if (event === "message") capturedHandler = cb;
    });
    const { getApi } = renderWithProvider();
    act(() => getApi().addRepo(REPO_A));
    await act(async () => {
      await getApi().startExtraction(REPO_A, true);
    });
    act(() => {
      capturedHandler?.({ task_id: "task-123", status: "scanning", progress: 0.5, message: "Scanning..." });
    });
    const repo = getApi().repos[0];
    expect(repo.status).toBe("scanning");
    expect(repo.progress).toBe(0.5);
    expect(repo.message).toBe("Scanning...");
  });

  it("ignores WS message for unknown taskId", async () => {
    let capturedHandler: ((data?: unknown) => void) | undefined;
    (wsService.on as any).mockImplementation((event: string, cb: (data?: unknown) => void) => {
      if (event === "message") capturedHandler = cb;
    });
    const { getApi } = renderWithProvider();
    act(() => {
      capturedHandler?.({ task_id: "unknown", status: "scanning" });
    });
    expect(getApi().repos).toEqual([]);
  });
});
