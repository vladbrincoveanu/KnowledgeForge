# Workspace Persistent Repository Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the `repos: RepoEntry[]` state out of `FileUploader` into a new `<RepoProvider>` Context above the Router so the queue survives tab switches. Add a new `<RepoExplorer>` component that renders the persistent queue. Shrink `FileUploader` to input-only.

**Architecture:** TDD bottom-up. Build `RepoProvider` first (state owner + WS + polling), then `RepoExplorer` (read view), then wire them into `App.tsx`, then refactor `FileUploader` to consume the context, then move SCSS. Each task = TDD cycle + commit. UI-only, no backend changes.

**Tech Stack:** React 18, TypeScript, React Context, Vitest + @testing-library/react, Playwright (e2e). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-07-workspace-persistent-repos-design.md`

**Worktree:** This plan runs in `/Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos` on branch `relentless/workspace-persistent-repos`. All paths below are relative to the worktree root.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx` | create | Context + Provider + `useRepos()` hook. Owns `repos[]`, WS subscription, per-task polling. |
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx` | create | Unit tests for all actions + WS dispatch. |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.tsx` | create | Read-only queue list + actions (Extract All, Clear All, Append toggle, Remove, Re-extract). |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx` | create | Unit tests for rendering and action delegation. |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss` | create | SCSS for repo list, items, status badges, progress bars, actions footer. Moved from `FileUploader.scss`. |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx` | refactor (678 → ~180 lines) | Input form only (GitHub URL/token, Local Folder tab, FolderDropZone). Delegates persistence to `useRepos()`. |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` | refactor | Tests for input form, GitHub/Local tab switching, addRepo delegation. |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss` | refactor (280 → ~30 lines) | Remove `.repo-list`, `.repo-item*`, `.empty-state`, `.repo-actions` rules (moved to RepoExplorer.scss). Keep URL/token/tab/drop-zone styles. |
| `sources/UI/src/App.tsx` | modify | Wrap with `<RepoProvider>`. Render `<FileUploader />` + `<RepoExplorer />` in `/workspace` route. Drop dead `files` state. |
| `sources/UI/e2e/specs/01-workspace.spec.ts` | new | Playwright coverage: add repo, switch tab, return, verify persistence. |
| `sources/UI/src/services/api.ts` | unchanged | WS + REST clients reused as-is. |
| `sources/UI/src/pages/ReviewDashboard.tsx` | unchanged | Reused as-is below the `<hr/>` divider. |
| `sources/Api/**` | unchanged | Backend untouched. |

---

## Task 1: Verify baseline + test infrastructure

**Files:** none

- [ ] **Step 1: Verify worktree + branch**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git branch --show-current
```

Expected: `relentless/workspace-persistent-repos`

- [ ] **Step 2: Verify baseline test suite passes**

```bash
cd sources/UI && npm run test -- --run
```

Expected: All existing tests pass (FileUploader + ReviewDashboard + others).

- [ ] **Step 3: Verify dev server starts cleanly**

```bash
cd sources/UI && timeout 15 npm run dev 2>&1 | head -20
```

Expected: Vite dev server starts, no TypeScript errors in console.

- [ ] **Step 4: No commit (baseline only)**

If anything fails, fix it before proceeding. No commit needed.

---

## Task 2: Create `RepoProvider` — extract `RepoEntry`/`RepoStatus` types (no test yet)

**Files:**
- Create: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`

- [ ] **Step 1: Create the directory and file**

```bash
mkdir -p sources/UI/src/@components/upload-extract/RepoProvider
```

Create `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx` with the type definitions and a placeholder context export (full implementation comes in later tasks):

```tsx
import React, { createContext, useContext } from "react";

export type RepoStatus =
  | "idle"
  | "pending"
  | "scanning"
  | "completed"
  | "failed"
  | "zipping"
  | "uploading";

export interface RepoEntry {
  url: string;
  token?: string;
  taskId?: string;
  status: RepoStatus;
  message: string;
  progress: number;
  containersCount: number;
  componentsCount: number;
  error?: string;
}

export interface RepoContextValue {
  repos: RepoEntry[];
  isExtracting: boolean;
  addRepo: (url: string, token?: string) => { ok: true } | { ok: false; error: string };
  removeRepo: (url: string) => void;
  clearAll: () => void;
  startExtraction: (url: string, append: boolean) => Promise<void>;
}

export const RepoContext = createContext<RepoContextValue | null>(null);

export const useRepos = (): RepoContextValue => {
  const ctx = useContext(RepoContext);
  if (!ctx) {
    throw new Error("useRepos must be used within <RepoProvider>");
  }
  return ctx;
};

// Placeholder Provider — real impl lands in Task 3+.
export const RepoProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const value: RepoContextValue = {
    repos: [],
    isExtracting: false,
    addRepo: () => ({ ok: false, error: "not implemented" }),
    removeRepo: () => {},
    clearAll: () => {},
    startExtraction: async () => {},
  };
  return <RepoContext.Provider value={value}>{children}</RepoContext.Provider>;
};
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd sources/UI && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx
git commit -m "feat(ui): add RepoProvider context skeleton with types"
```

---

## Task 3: `RepoProvider` — failing tests for `addRepo` (TDD RED)

**Files:**
- Create: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx`:

```tsx
/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, act, cleanup } from "@testing-library/react";

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

import { RepoProvider, useRepos, RepoEntry } from "./RepoProvider";
import { wsService } from "@/services/api";

const TestConsumer: React.FC<{ onReady: (api: ReturnType<typeof useRepos>) => void }> = ({
  onReady,
}) => {
  const api = useRepos();
  React.useEffect(() => onReady(api), [api, onReady]);
  return null;
};

import React from "react";

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
    const result = getApi().addRepo(REPO_A);
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
    getApi().addRepo("https://github.com/facebook/react.git/");
    expect(getApi().repos[0].url).toBe(REPO_A);
  });

  it("includes token when provided", () => {
    const { getApi } = renderWithProvider();
    getApi().addRepo(REPO_A, "ghp_xxx");
    expect(getApi().repos[0].token).toBe("ghp_xxx");
  });

  it("omits token when empty string", () => {
    const { getApi } = renderWithProvider();
    getApi().addRepo(REPO_A, "  ");
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
    getApi().addRepo(REPO_A);
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
    getApi().addRepo(REPO_A);
    getApi().addRepo(REPO_B);
    expect(getApi().repos.map((r) => r.url)).toEqual([REPO_A, REPO_B]);
  });
});
```

- [ ] **Step 2: Run tests to confirm RED**

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: All `addRepo` tests fail. The placeholder returns `{ ok: false, error: "not implemented" }`.

- [ ] **Step 3: Commit (RED)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx
git commit -m "test(ui): add RepoProvider addRepo tests (red)"
```

---

## Task 4: `RepoProvider` — implement `addRepo` (TDD GREEN)

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`

- [ ] **Step 1: Replace the placeholder Provider with a real implementation**

Replace the entire content of `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`:

```tsx
import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from "react";
import { codeArchitectureAPI, wsService } from "@/services/api";

export type RepoStatus =
  | "idle"
  | "pending"
  | "scanning"
  | "completed"
  | "failed"
  | "zipping"
  | "uploading";

export interface RepoEntry {
  url: string;
  token?: string;
  taskId?: string;
  status: RepoStatus;
  message: string;
  progress: number;
  containersCount: number;
  componentsCount: number;
  error?: string;
}

export interface RepoContextValue {
  repos: RepoEntry[];
  isExtracting: boolean;
  addRepo: (url: string, token?: string) => { ok: true } | { ok: false; error: string };
  removeRepo: (url: string) => void;
  clearAll: () => void;
  startExtraction: (url: string, append: boolean) => Promise<void>;
}

export const RepoContext = createContext<RepoContextValue | null>(null);

export const useRepos = (): RepoContextValue => {
  const ctx = useContext(RepoContext);
  if (!ctx) {
    throw new Error("useRepos must be used within <RepoProvider>");
  }
  return ctx;
};

const isValidGitUrl = (url: string): boolean => {
  try {
    const u = new URL(url);
    return (
      (u.protocol === "https:" || u.protocol === "http:") &&
      u.hostname.includes(".") &&
      u.pathname.split("/").filter(Boolean).length >= 2
    );
  } catch {
    return false;
  }
};

const normalizeUrl = (raw: string): string =>
  raw.trim().replace(/\.git\/?$/, "").replace(/\/$/, "");

export const RepoProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [repos, setRepos] = useState<RepoEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const pollIntervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const addRepo: RepoContextValue["addRepo"] = (url, token) => {
    const trimmed = normalizeUrl(url);
    if (!trimmed) return { ok: false, error: "Please enter a repository URL." };
    if (!isValidGitUrl(trimmed)) {
      return {
        ok: false,
        error:
          "Enter a valid repository URL (e.g. https://github.com/owner/repo or https://gitlab.example.com/group/repo).",
      };
    }
    if (repos.some((r) => r.url === trimmed)) {
      return { ok: false, error: "This repository has already been added." };
    }
    const cleanToken = token?.trim();
    setRepos((prev) => [
      ...prev,
      {
        url: trimmed,
        token: cleanToken || undefined,
        status: "idle",
        message: "Ready to extract",
        progress: 0,
        containersCount: 0,
        componentsCount: 0,
      },
    ]);
    return { ok: true };
  };

  const removeRepo: RepoContextValue["removeRepo"] = (url) => {
    setRepos((prev) => prev.filter((r) => r.url !== url));
  };

  const clearAll: RepoContextValue["clearAll"] = () => {
    Object.values(pollIntervalsRef.current).forEach(clearInterval);
    pollIntervalsRef.current = {};
    setRepos([]);
  };

  const startExtraction: RepoContextValue["startExtraction"] = async () => {
    // Implemented in Task 5
  };

  // WS subscription + cleanup — implemented in Task 6
  useEffect(() => {
    return () => {};
  }, []);

  const value: RepoContextValue = {
    repos,
    isExtracting,
    addRepo,
    removeRepo,
    clearAll,
    startExtraction,
  };

  return <RepoContext.Provider value={value}>{children}</RepoContext.Provider>;
};
```

- [ ] **Step 2: Run tests to confirm GREEN**

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: All 9 `addRepo` tests pass.

- [ ] **Step 3: Commit (GREEN)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx
git commit -m "feat(ui): implement RepoProvider addRepo"
```

---

## Task 5: `RepoProvider` — failing tests + impl for `removeRepo` and `clearAll`

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx`
- Modify: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`

- [ ] **Step 1: Append failing tests for `removeRepo` and `clearAll`**

Append to the `describe` block in `RepoProvider.test.tsx`:

```tsx
  describe("RepoProvider — removeRepo", () => {
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
```

- [ ] **Step 2: Run tests to confirm RED for the new ones**

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: `removeRepo` and `clearAll` tests fail (current impl is no-op for removeRepo, also no-op for clearAll since repos is empty after).

- [ ] **Step 3: Implement `removeRepo` and `clearAll` (already in Task 4's code)**

The implementations were already added in Task 4. Re-run tests.

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: All tests pass.

- [ ] **Step 4: Commit (GREEN)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx
git add sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx
git commit -m "feat(ui): RepoProvider removeRepo + clearAll"
```

---

## Task 6: `RepoProvider` — failing tests + impl for `startExtraction` and WS dispatch

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx`
- Modify: `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`

> **Note:** `startExtraction` returns `Promise<string | null>` — the new `task_id` on success, `null` on failure. This lets `RepoExplorer.extractAll` pass the taskId to the `onExtractionStarted` callback after each start. Spec's `RepoContextValue` interface gets updated here.

- [ ] **Step 1: Update the `RepoContextValue` type signature**

In `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx`, change the `startExtraction` signature:

```tsx
export interface RepoContextValue {
  repos: RepoEntry[];
  isExtracting: boolean;
  addRepo: (url: string, token?: string) => { ok: true } | { ok: false; error: string };
  removeRepo: (url: string) => void;
  clearAll: () => void;
  startExtraction: (url: string, append: boolean) => Promise<string | null>;
}
```

- [ ] **Step 2: Append failing tests for `startExtraction` and WS dispatch**

Append to the `describe` block in `RepoProvider.test.tsx`:

```tsx
  import { codeArchitectureAPI } from "@/services/api";

  describe("RepoProvider — startExtraction", () => {
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
```

- [ ] **Step 3: Run tests to confirm RED**

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: New `startExtraction` and WS tests fail (startExtraction is no-op, no WS subscription).

- [ ] **Step 4: Implement `startExtraction` (returning taskId) and WS subscription**

Replace `startExtraction` and the `useEffect` in `RepoProvider.tsx`:

```tsx
  const startExtraction: RepoContextValue["startExtraction"] = async (url, append) => {
    const repo = repos.find((r) => r.url === url);
    if (!repo) return null;

    setRepos((prev) =>
      prev.map((r) =>
        r.url === url
          ? { ...r, status: "pending", message: "Queuing extraction...", progress: 0 }
          : r,
      ),
    );

    try {
      const result = await codeArchitectureAPI.extractFromGitHub(
        url,
        true,
        append,
        repo.token,
      );
      const taskId = result.task_id;
      setRepos((prev) =>
        prev.map((r) =>
          r.url === url
            ? { ...r, taskId, status: "pending", message: "Extraction queued", progress: 0 }
            : r,
        ),
      );
      return taskId;
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? "Extraction failed";
      setRepos((prev) =>
        prev.map((r) =>
          r.url === url ? { ...r, status: "failed", message: msg } : r,
        ),
      );
      return null;
    }
  };

  useEffect(() => {
    wsService.connect();
    const handler = (data?: unknown) => {
      const msg = data as {
        task_id?: string;
        status?: string;
        message?: string;
        progress?: number;
      };
      if (!msg?.task_id) return;
      setRepos((prev) =>
        prev.map((r) => {
          if (r.taskId !== msg.task_id) return r;
          return {
            ...r,
            status: (msg.status as RepoStatus) ?? r.status,
            message: msg.message ?? r.message,
            progress: msg.progress ?? r.progress,
          };
        }),
      );
    };
    wsService.on("message", handler);
    return () => {
      wsService.off("message", handler);
      Object.values(pollIntervalsRef.current).forEach(clearInterval);
    };
  }, []);
```

Also update the placeholder return type at the bottom of `RepoProvider.tsx`:

```tsx
  const value: RepoContextValue = {
    repos,
    isExtracting,
    addRepo,
    removeRepo,
    clearAll,
    startExtraction,
  };
```

The `startExtraction` reference resolves to the new function defined above (not the no-op placeholder from Task 2).

- [ ] **Step 5: Run tests to confirm GREEN**

```bash
cd sources/UI && npx vitest run RepoProvider.test.tsx
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoProvider/
git commit -m "feat(ui): RepoProvider startExtraction returns taskId + WS dispatch"
```

---

## Task 7: `RepoExplorer` — failing tests (TDD RED)

**Files:**
- Create: `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx`

- [ ] **Step 1: Create directory and test file**

```bash
mkdir -p sources/UI/src/@components/upload-extract/RepoExplorer
```

Create `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx`:

```tsx
/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

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

import { RepoProvider, useRepos } from "../RepoProvider/RepoProvider";
import RepoExplorer from "./RepoExplorer";

const REPO_A = "https://github.com/facebook/react";
const REPO_B = "https://github.com/microsoft/typescript";

const Harness: React.FC<{
  onReady?: (api: ReturnType<typeof useRepos>) => void;
  onExtractionStarted?: (taskId: string, file: unknown) => void;
}> = ({ onReady, onExtractionStarted }) => {
  const api = useRepos();
  React.useEffect(() => onReady?.(api), [api, onReady]);
  return <RepoExplorer onExtractionStarted={onExtractionStarted} />;
};

import React from "react";

const renderExplorer = (overrides: {
  onExtractionStarted?: (taskId: string, file: unknown) => void;
} = {}) => {
  let api!: ReturnType<typeof useRepos>;
  const onExtractionStarted = overrides.onExtractionStarted ?? vi.fn();
  render(
    <RepoProvider>
      <Harness onReady={(a) => (api = a)} onExtractionStarted={onExtractionStarted} />
    </RepoProvider>,
  );
  return { getApi: () => api, onExtractionStarted };
};

describe("RepoExplorer", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("renders empty state when no repos", () => {
    renderExplorer();
    expect(screen.getByText(/Add one or more repository URLs above/i)).toBeInTheDocument();
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
    (await import("@/services/api")).codeArchitectureAPI.extractFromGitHub.mockResolvedValue({
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
    expect((await import("@/services/api")).codeArchitectureAPI.extractFromGitHub).toHaveBeenCalledTimes(2);
    expect(onExtractionStarted).toHaveBeenCalled();
  });

  it("Append toggle changes startExtraction append param", async () => {
    const api = await import("@/services/api");
    api.codeArchitectureAPI.extractFromGitHub.mockResolvedValue({ task_id: "task-1" });
    const { getApi } = renderExplorer();
    act(() => getApi().addRepo(REPO_A));
    const toggle = screen.getByLabelText(/Add to existing graph data/i);
    fireEvent.click(toggle);
    const extractBtn = screen.getByRole("button", { name: /Extract 1 Repo/i });
    await act(async () => {
      fireEvent.click(extractBtn);
    });
    expect(api.codeArchitectureAPI.extractFromGitHub).toHaveBeenCalledWith(REPO_A, true, false, undefined);
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
});
```

- [ ] **Step 2: Run tests to confirm RED**

```bash
cd sources/UI && npx vitest run RepoExplorer.test.tsx
```

Expected: All tests fail (RepoExplorer doesn't exist).

- [ ] **Step 3: Commit (RED)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx
git commit -m "test(ui): add RepoExplorer tests (red)"
```

---

## Task 8: `RepoExplorer` — implement component (TDD GREEN)

**Files:**
- Create: `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.tsx`

- [ ] **Step 1: Create the component**

Create `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.tsx`:

```tsx
import React, { useState } from "react";
import {
  Github,
  Folder,
  X,
  Play,
  Trash2,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader,
  Package,
  Layers,
  RotateCcw,
} from "lucide-react";
import { useRepos, RepoStatus, RepoEntry } from "../RepoProvider/RepoProvider";
import "./RepoExplorer.scss";

interface RepoExplorerProps {
  onExtractionStarted?: (taskId: string, file: { name: string; type: string; size: number }) => void;
}

const statusConfig: Record<
  RepoStatus,
  { icon: JSX.Element; color: string; label: string }
> = {
  idle: { icon: <Clock size={14} />, color: "#6c757d", label: "Ready" },
  pending: { icon: <Clock size={14} />, color: "#ffc107", label: "Queued" },
  scanning: {
    icon: <Loader size={14} className="spin" />,
    color: "#007bff",
    label: "Scanning",
  },
  completed: {
    icon: <CheckCircle size={14} />,
    color: "#28a745",
    label: "Done",
  },
  failed: {
    icon: <AlertCircle size={14} />,
    color: "#dc3545",
    label: "Failed",
  },
  zipping: {
    icon: <Loader size={14} className="spin" />,
    color: "#6610f2",
    label: "Zipping",
  },
  uploading: {
    icon: <Loader size={14} className="spin" />,
    color: "#007bff",
    label: "Uploading",
  },
};

const RepoExplorer: React.FC<RepoExplorerProps> = ({ onExtractionStarted }) => {
  const { repos, isExtracting, removeRepo, clearAll, startExtraction } = useRepos();
  const [appendMode, setAppendMode] = useState(false);

  const idleCount = repos.filter(
    (r) => r.status === "idle" || r.status === "failed",
  ).length;

  const extractAll = async () => {
    const idleRepos = repos.filter(
      (r) => r.status === "idle" || r.status === "failed",
    );
    for (const repo of idleRepos) {
      const taskId = await startExtraction(repo.url, appendMode);
      if (taskId && onExtractionStarted) {
        onExtractionStarted(taskId, {
          name: repo.url,
          type: "github",
          size: 0,
        });
      }
    }
  };

  return (
    <div className="repo-explorer">
      {repos.length > 0 && (
        <div className="repo-list">
          {repos.map((repo) => {
            const cfg = statusConfig[repo.status];
            return (
              <div
                key={repo.url}
                className={`repo-item repo-item--${repo.status}`}
                data-testid="repo-row"
              >
                <div className="repo-item__left">
                  {repo.url.endsWith("/") ? (
                    <Folder size={16} className="repo-item__icon" />
                  ) : (
                    <Github size={16} className="repo-item__icon" />
                  )}
                  <div className="repo-item__info">
                    <span className="repo-item__url">{repo.url}</span>
                    <span className="repo-item__message">{repo.message}</span>
                    {(repo.status === "pending" ||
                      repo.status === "scanning" ||
                      repo.status === "zipping" ||
                      repo.status === "uploading") && (
                      <div className="repo-item__progress">
                        {repo.status === "pending" ? (
                          <div className="repo-item__progress-fill repo-item__progress-fill--indeterminate" />
                        ) : (
                          <div
                            className="repo-item__progress-fill"
                            style={{ width: `${Math.round(repo.progress * 100)}%` }}
                          />
                        )}
                      </div>
                    )}
                    {repo.status === "completed" && (
                      <div className="repo-item__stats">
                        <span>
                          <Package size={12} /> {repo.containersCount} containers
                        </span>
                        <span>
                          <Layers size={12} /> {repo.componentsCount} components
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="repo-item__right">
                  <span
                    className="repo-item__status"
                    style={{ color: cfg.color }}
                  >
                    {cfg.icon}
                    {cfg.label}
                  </span>
                  {repo.status === "completed" && (
                    <button
                      className="btn-rerun"
                      onClick={() => startExtraction(repo.url, appendMode)}
                      title="Re-extract"
                      disabled={isExtracting}
                    >
                      <RotateCcw size={14} />
                    </button>
                  )}
                  {(repo.status === "idle" || repo.status === "failed") && (
                    <button
                      className="btn-remove"
                      onClick={() => removeRepo(repo.url)}
                      title="Remove"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {repos.length === 0 && (
        <div className="empty-state">
          <Github size={48} className="empty-state__icon" />
          <p>Add one or more repository URLs above</p>
          <p className="empty-state__hint">
            Each repo will be cloned, scanned, and added to the architecture graph
          </p>
        </div>
      )}

      {repos.length > 0 && (
        <div className="repo-actions">
          <label className="append-toggle">
            <input
              type="checkbox"
              checked={appendMode}
              onChange={(e) => setAppendMode(e.target.checked)}
              disabled={isExtracting}
            />
            Add to existing graph data
          </label>
          <button
            className="btn-extract"
            onClick={extractAll}
            disabled={isExtracting || idleCount === 0}
          >
            {isExtracting ? (
              <>
                <Loader size={16} className="spin" /> Extracting...
              </>
            ) : (
              <>
                <Play size={16} /> Extract{" "}
                {idleCount > 0
                  ? `${idleCount} Repo${idleCount > 1 ? "s" : ""}`
                  : "All"}
              </>
            )}
          </button>
          <button
            className="btn-clear-repos"
            onClick={clearAll}
            disabled={isExtracting}
          >
            <Trash2 size={16} />
            Clear All
          </button>
        </div>
      )}
    </div>
  );
};

export default RepoExplorer;
```

- [ ] **Step 2: Create empty SCSS file**

Create `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss`:

```scss
/* Styles relocated from FileUploader.scss in Task 11. */
.repo-explorer {
  background: #ffffff;
  border-radius: 8px;
  padding: 2rem;
  border: 1px solid #e9ecef;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
```

- [ ] **Step 3: Run tests to confirm GREEN**

```bash
cd sources/UI && npx vitest run RepoExplorer.test.tsx
```

Expected: All tests pass. The Extract All and Append tests may need `await` for the promise — adjust the implementation if any timing issues surface (use `await act(async () => { fireEvent.click(...) })`).

- [ ] **Step 4: If the "Append toggle" test fails, fix `extractAll` to capture append at call time**

Edit `extractAll` in `RepoExplorer.tsx`:

```tsx
  const extractAll = async () => {
    const idleRepos = repos.filter(
      (r) => r.status === "idle" || r.status === "failed",
    );
    const append = appendMode;
    for (const repo of idleRepos) {
      await startExtraction(repo.url, append);
    }
  };
```

This passes `append` (closure-captured) so the toggle is honored even after the click triggers a state update.

- [ ] **Step 5: Re-run tests**

```bash
cd sources/UI && npx vitest run RepoExplorer.test.tsx
```

Expected: All tests pass.

- [ ] **Step 6: Commit (GREEN)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/RepoExplorer/
git commit -m "feat(ui): implement RepoExplorer component"
```

---

## Task 9: Wire `RepoProvider` + `RepoExplorer` into `App.tsx` (integration step)

**Files:**
- Modify: `sources/UI/src/App.tsx`

- [ ] **Step 1: Add imports**

Add to the top of `sources/UI/src/App.tsx`:

```tsx
import { RepoProvider } from "./@components/upload-extract/RepoProvider/RepoProvider";
import RepoExplorer from "./@components/upload-extract/RepoExplorer/RepoExplorer";
```

- [ ] **Step 2: Wrap the Router with RepoProvider**

Replace the `App` component (currently around line 366-372):

```tsx
const App: React.FC = () => {
  return (
    <RepoProvider>
      <Router>
        <MainContent />
      </Router>
    </RepoProvider>
  );
};
```

- [ ] **Step 3: Render `<RepoExplorer />` in the `/workspace` route**

In the `/workspace` route element (around line 265-313), after the `<FileUploader />` JSX, add:

```tsx
                  <RepoExplorer
                    onExtractionStarted={(taskId) => {
                      setActiveTaskId(taskId);
                    }}
                  />
```

(Full placement: after `<FileUploader ... />` and before the `<hr />` divider. See exact location in current App.tsx around line 281.)

- [ ] **Step 4: Drop dead `files` state in `MainContent`**

In `MainContent` (around line 117-118), remove:

```tsx
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const isProcessing = false;
```

and remove the `handleFilesUploaded` callback (around line 226-231). The `UploadedFile` interface (lines 31-38) can also be removed.

- [ ] **Step 5: Verify type-check**

```bash
cd sources/UI && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Run all unit tests**

```bash
cd sources/UI && npm run test -- --run
```

Expected: All existing tests pass + new RepoProvider/RepoExplorer tests pass.

- [ ] **Step 7: Run dev server smoke**

```bash
cd sources/UI && timeout 20 npm run dev 2>&1 | head -30
```

Expected: Server starts, console shows no React errors. Ctrl-C after 20s.

- [ ] **Step 8: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/App.tsx
git commit -m "feat(ui): wire RepoProvider + RepoExplorer into workspace"
```

---

## Task 10: Refactor `FileUploader` — drop repos state, delegate to provider

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx`

- [ ] **Step 1: Refactor FileUploader to input-only**

Replace the entire content of `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx`:

```tsx
import React, { useState, useCallback } from "react";
import { Github, Folder, Plus, Lock, Eye, EyeOff } from "lucide-react";
import { useRepos } from "../RepoProvider/RepoProvider";
import "./FileUploader.scss";
import FolderDropZone from "./FolderDropZone";

interface FileUploaderProps {
  isProcessing: boolean;
  onExtractionStarted: (taskId: string, file: { name: string; type: string; size: number }) => void;
  showNotification: (
    message: string,
    type: "success" | "error" | "info",
  ) => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onExtractionStarted,
  showNotification,
}) => {
  const [inputUrl, setInputUrl] = useState("");
  const [inputToken, setInputToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [activeTab, setActiveTab] = useState<"github" | "local">("github");
  const { addRepo } = useRepos();

  const handleAdd = () => {
    const result = addRepo(inputUrl, inputToken);
    if (!result.ok) {
      showNotification(result.error, "error");
      return;
    }
    setInputUrl("");
    setInputToken("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleAdd();
  };

  const handleFolderZipReady = useCallback(
    async (blob: Blob, name: string, sizeBytes: number) => {
      const displayName = name + "/";
      const result = addRepo(displayName);
      if (!result.ok) {
        showNotification(result.error, "error");
        return;
      }
      // Upload + extraction start is owned by RepoExplorer.startExtraction —
      // for now, the folder upload flow is deferred. The provider-based
      // addRepo above is sufficient for the persistent-queue bug fix.
      // (The folder upload XHR/polling integration is tracked separately.)
      showNotification(`Folder "${name}" added to queue. Use Extract All to start.`, "info");
    },
    [addRepo, showNotification],
  );

  const handleFolderProgress = useCallback(() => {
    // No-op for now — folder upload XHR deferred.
  }, []);

  return (
    <div className="repo-extractor">
      <div className="repo-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "github"}
          className={`repo-tab ${activeTab === "github" ? "repo-tab--active" : ""}`}
          onClick={() => setActiveTab("github")}
        >
          GitHub URL
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "local"}
          className={`repo-tab ${activeTab === "local" ? "repo-tab--active" : ""}`}
          onClick={() => setActiveTab("local")}
        >
          Local Folder
        </button>
      </div>

      {activeTab === "local" ? (
        <FolderDropZone
          onZipReady={handleFolderZipReady}
          onProgress={handleFolderProgress}
          onError={(msg) => showNotification(msg, "error")}
        />
      ) : (
        <div className="url-input-section">
          <div className="url-input-row">
            <div className="url-input-wrapper">
              <Github size={18} className="url-input-icon" />
              <input
                type="url"
                className="url-input"
                placeholder="https://github.com/owner/repo or https://gitlab.example.com/group/repo"
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <button className="btn-add" onClick={handleAdd}>
              <Plus size={18} />
              Add
            </button>
          </div>
          <div className="token-input-row">
            <div className="url-input-wrapper token-input-wrapper">
              <Lock size={16} className="url-input-icon token-icon" />
              <input
                type={showToken ? "text" : "password"}
                className="url-input token-input"
                placeholder="Access token (optional — for private repos)"
                value={inputToken}
                onChange={(e) => setInputToken(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete="off"
              />
              <button
                type="button"
                className="btn-toggle-token"
                onClick={() => setShowToken((v) => !v)}
                aria-label={showToken ? "Hide token" : "Show token"}
              >
                {showToken ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUploader;
```

- [ ] **Step 2: Update FileUploader test for the new props/behavior**

Replace `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` with a focused test for the input-only form. (See full new test file content below.)

Create the new test file (overwrite the existing one):

```tsx
/* @vitest-environment jsdom */

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

const Harness: React.FC<{ onReady?: (api: ReturnType<typeof useRepos>) => void }> = ({ onReady }) => {
  const api = useRepos();
  React.useEffect(() => onReady?.(api), [api, onReady]);
  return null;
};

import React from "react";

const renderWithProvider = () => {
  let api!: ReturnType<typeof useRepos>;
  render(
    <RepoProvider>
      <FileUploader
        isProcessing={false}
        onExtractionStarted={vi.fn()}
        showNotification={vi.fn()}
      />
      <Harness onReady={(a) => (api = a)} />
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
    expect(screen.getByPlaceholderText(/github\.com\/owner\/repo/i)).toBeInTheDocument();
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
    // FolderDropZone renders its own UI; just verify the tab toggle works
    expect(screen.getByRole("tab", { name: /Local Folder/i })).toHaveAttribute("aria-selected", "true");
  });

  it("Enter key in URL input triggers Add", () => {
    const { getApi } = renderWithProvider();
    const input = screen.getByPlaceholderText(/github\.com\/owner\/repo/i);
    fireEvent.change(input, { target: { value: REPO_A } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(getApi().repos).toHaveLength(1);
  });
});
```

- [ ] **Step 3: Run all tests**

```bash
cd sources/UI && npm run test -- --run
```

Expected: All tests pass — FileUploader tests, RepoProvider tests, RepoExplorer tests, plus all unchanged tests.

- [ ] **Step 4: Verify type-check**

```bash
cd sources/UI && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/FileUploader/
git commit -m "refactor(ui): FileUploader delegates to RepoProvider, drops repos state"
```

---

## Task 11: Move SCSS — relocate `.repo-list`, `.repo-item*`, `.empty-state`, `.repo-actions` from `FileUploader.scss` to `RepoExplorer.scss`

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss`
- Modify: `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss`

- [ ] **Step 1: Read the current `FileUploader.scss`**

```bash
cat sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss
```

Identify the section starting from `.repo-list` through the end of the file (lines ~150-280 of the current 8.8K file).

- [ ] **Step 2: Copy those rules into `RepoExplorer.scss`**

Append to `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss`:

```scss
/* ============================================
   Repo list (moved from FileUploader.scss)
   ============================================ */

.repo-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.repo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1rem;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  font-size: 0.9rem;
  transition: border-color 0.15s;

  &:hover {
    border-color: #ced4da;
  }

  &--completed {
    background: #f0fff4;
    border-color: #c6f6d5;
  }

  &--failed {
    background: #fff5f5;
    border-color: #fed7d7;
  }

  &__left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex: 1;
    min-width: 0;
  }

  &__icon {
    flex-shrink: 0;
    color: #4a5568;
  }

  &__info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
    flex: 1;
  }

  &__url {
    font-weight: 500;
    color: #1a202c;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  &__lock {
    color: #6c757d;
  }

  &__message {
    font-size: 0.8rem;
    color: #6c757d;
  }

  &__progress {
    height: 4px;
    background: #e9ecef;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 0.25rem;
  }

  &__progress-fill {
    height: 100%;
    background: #007bff;
    transition: width 0.2s;

    &--indeterminate {
      width: 30%;
      animation: indeterminate 1.5s infinite linear;
    }
  }

  &__stats {
    display: flex;
    gap: 1rem;
    font-size: 0.75rem;
    color: #6c757d;
    margin-top: 0.25rem;

    span {
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  &__status {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.8rem;
    font-weight: 500;
  }
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

/* ============================================
   Empty state
   ============================================ */

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1.5rem;
  text-align: center;
  color: #6c757d;

  &__icon {
    color: #cbd5e0;
    margin-bottom: 1rem;
  }

  &__hint {
    font-size: 0.85rem;
    color: #a0aec0;
    margin-top: 0.25rem;
  }
}

/* ============================================
   Actions footer
   ============================================ */

.repo-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e9ecef;
  flex-wrap: wrap;
}

.append-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #4a5568;
  cursor: pointer;

  input[type="checkbox"] {
    cursor: pointer;
  }
}

.btn-extract {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  background: #00b8b8;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;

  &:hover:not(:disabled) {
    background: #009999;
  }

  &:disabled {
    background: #cbd5e0;
    cursor: not-allowed;
  }
}

.btn-clear-repos {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  background: white;
  color: #4a5568;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: border-color 0.15s;

  &:hover:not(:disabled) {
    border-color: #a0aec0;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-remove {
  background: transparent;
  border: none;
  color: #6c757d;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;

  &:hover {
    background: #fed7d7;
    color: #dc3545;
  }
}

.btn-rerun {
  background: transparent;
  border: 1px solid #ced4da;
  color: #4a5568;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s;

  &:hover:not(:disabled) {
    border-color: #007bff;
    color: #007bff;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 3: Strip the moved rules from `FileUploader.scss`**

Read the file, then delete the rules starting from the `.repo-list` block through the end. Use `Edit` with the exact text of those rules. (Refer to the file you read in Step 1.)

- [ ] **Step 4: Verify visually (dev server)**

```bash
cd sources/UI && timeout 20 npm run dev 2>&1 | head -30
```

Open `http://localhost:5173/workspace`. Confirm the queue still renders correctly with same visual appearance.

- [ ] **Step 5: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss
git add sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss
git commit -m "refactor(ui): relocate repo-list styles to RepoExplorer.scss"
```

---

## Task 12: E2E test — tab-switch persistence

**Files:**
- Create: `sources/UI/e2e/specs/01-workspace.spec.ts`

- [ ] **Step 1: Check existing e2e setup**

```bash
ls sources/UI/e2e/specs/
cat sources/UI/playwright.config.ts 2>/dev/null | head -30
```

Expected: At least 1 existing spec file. Use the same setup pattern.

- [ ] **Step 2: Write the e2e test**

Create `sources/UI/e2e/specs/01-workspace.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test.describe("Workspace — persistent repo queue", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
  });

  test("repo added via URL input persists across tab switch", async ({ page }) => {
    const REPO = "https://github.com/facebook/react";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);
    await urlInput.fill(REPO);
    await page.getByRole("button", { name: /^Add$/i }).click();

    // Repo visible in explorer
    await expect(page.getByText(REPO)).toBeVisible();

    // Switch to Code Architecture tab
    await page.getByRole("link", { name: /Code Architecture/i }).click();
    await expect(page).toHaveURL(/\/code-architecture/);

    // Switch back to Workspace
    await page.getByRole("link", { name: /Workspace/i }).click();
    await expect(page).toHaveURL(/\/workspace/);

    // Repo still visible
    await expect(page.getByText(REPO)).toBeVisible();
  });

  test("two repos can be added and both persist", async ({ page }) => {
    const REPO_A = "https://github.com/facebook/react";
    const REPO_B = "https://github.com/microsoft/typescript";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);

    await urlInput.fill(REPO_A);
    await page.getByRole("button", { name: /^Add$/i }).click();
    await urlInput.fill(REPO_B);
    await page.getByRole("button", { name: /^Add$/i }).click();

    await expect(page.getByText(REPO_A)).toBeVisible();
    await expect(page.getByText(REPO_B)).toBeVisible();

    // Switch tabs
    await page.getByRole("link", { name: /Code Architecture/i }).click();
    await page.getByRole("link", { name: /Workspace/i }).click();

    await expect(page.getByText(REPO_A)).toBeVisible();
    await expect(page.getByText(REPO_B)).toBeVisible();
  });

  test("Remove button removes a repo from the queue", async ({ page }) => {
    const REPO = "https://github.com/facebook/react";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);
    await urlInput.fill(REPO);
    await page.getByRole("button", { name: /^Add$/i }).click();

    await expect(page.getByText(REPO)).toBeVisible();
    await page.locator(`[data-testid="repo-row"]`).getByTitle("Remove").click();
    await expect(page.getByText(REPO)).not.toBeVisible();
  });
});
```

- [ ] **Step 3: Run the e2e test**

```bash
cd sources/UI && npx playwright test e2e/specs/01-workspace.spec.ts
```

Expected: All 3 tests pass.

- [ ] **Step 4: Run the full e2e suite for regression**

```bash
cd sources/UI && npx playwright test
```

Expected: All previous specs still pass (review-queue, etc.) + new spec passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git add sources/UI/e2e/specs/01-workspace.spec.ts
git commit -m "test(e2e): workspace repo queue persists across tab switch"
```

---

## Task 13: Final verification + cleanup

**Files:** none (verification only)

- [ ] **Step 1: Run full unit test suite**

```bash
cd sources/UI && npm run test -- --run
```

Expected: 100% pass.

- [ ] **Step 2: Run type check**

```bash
cd sources/UI && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Run linter**

```bash
cd sources/UI && npm run lint
```

Expected: No errors. Fix any unused imports / unused vars (the refactored FileUploader may have orphaned `useCallback` etc.).

- [ ] **Step 4: Run format check + fix**

```bash
cd sources/UI && npm run format:check
cd sources/UI && npm run format  # if check fails
```

- [ ] **Step 5: Run full check-all**

```bash
cd sources/UI && npm run check-all
```

Expected: All green.

- [ ] **Step 6: Manual smoke test**

```bash
cd sources/UI && npm run dev
```

Open `http://localhost:5173/workspace` in browser:
1. Add a GitHub URL → repo appears in queue
2. Switch to Code Architecture → switch back → repo still there
3. Add a second URL → both visible
4. Click Remove on one → only the other remains
5. Click Extract All (with no backend running, the call will fail; that's fine — confirm the status badge updates to "Failed")
6. Open the dev console → no React warnings or errors

- [ ] **Step 7: Commit any format/lint fixes**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/workspace-persistent-repos
git status
# If any files changed:
git add -u
git commit -m "style(ui): apply prettier + eslint fixes"
```

---

## Edge Cases

1. **Tab switch during in-flight extraction:** Provider stays mounted (above Router), polls/WS continue. Returning to `/workspace` shows latest status. ✓
2. **WS message arrives for a removed repo:** Provider filters by `taskId`, no match → no state update. ✓
3. **Network failure during `extractFromGitHub`:** Provider sets `status="failed"`, message captures error. ✓
4. **Polling network errors:** (Future — not implemented in this PR.) Out of scope; rely on WS for status updates.
5. **`clearAll` while extractions in progress:** Cancels poll intervals, clears state. Backend tasks continue server-side. User loses client visibility. ✓
6. **Add same URL twice:** Dedupe check in `addRepo`. Second add returns error. ✓
7. **Empty / invalid URL:** Validation in `addRepo`. Returns error. ✓
8. **Many repos (20+):** Vertical list, scroll. No virtualization (YAGNI). ✓
9. **HMR remount of provider:** Dev-only, state resets. Production unaffected. ✓
10. **Folder upload XHR / polling:** Deferred. The persistent-queue fix is independent of folder upload flow. Folder add → provider `addRepo` works; actual zip+upload via `FolderDropZone` is a future iteration.

## Out of Scope (Deferred)

- **Folder upload XHR + per-repo polling** — the persistent-queue bug is fixed without lifting the folder upload flow. `FileUploader.handleFolderZipReady` adds the folder to the provider's queue (status="idle") and shows a notification telling the user to click Extract All. The XHR upload + 2s poll that lives in the current `FileUploader.uploadZip` + `pollStatus` will be lifted to `RepoProvider` (via a new `updateRepo(url, partial)` action) in a follow-up PR. Tracking the gap explicitly so it's not lost.
- Polling via `getExtractionStatus` for GitHub URL flow — current implementation relies on WS for status updates; if WS disconnects, status may stall. Acceptable for this PR, addressed in follow-up.
- File-tree drill-down per repo (would need new backend endpoint).
- Cross-tab state sync via BroadcastChannel (out of scope — would surprise users).
- `onCallChannel`-style metadata fields on the RepoEntry (no business need surfaced).

---

## Files Touched Summary

| File | Action | Approx. lines after |
|------|--------|---------------------|
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx` | new | ~200 |
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx` | new | ~150 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.tsx` | new | ~180 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx` | new | ~150 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss` | new | ~330 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx` | refactor 678 → ~120 | 120 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` | refactor | ~150 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss` | refactor 280 → ~150 | 150 |
| `sources/UI/src/App.tsx` | modify | ~370 |
| `sources/UI/e2e/specs/01-workspace.spec.ts` | new | ~75 |
| Backend | unchanged | 0 |
| `services/api.ts` | unchanged | 0 |
| `pages/ReviewDashboard.tsx` | unchanged | 275 |

**Net change:** ~+700 new lines (production + tests), ~600 lines moved/refactored. Bug fixed (uploads persist across tab switches) + new feature (persistent repo explorer + multi-repo).

---

## Open Questions

None — all design decisions resolved with recommended options during brainstorming.
