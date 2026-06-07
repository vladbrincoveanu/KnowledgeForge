import React, {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  useCallback,
} from "react";
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
  addRepo: (
    url: string,
    token?: string,
  ) => { ok: true } | { ok: false; error: string };
  removeRepo: (url: string) => void;
  clearAll: () => void;
  startExtraction: (url: string, append: boolean) => Promise<string | null>;
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
  raw
    .trim()
    .replace(/\.git\/?$/, "")
    .replace(/\/$/, "");

export const RepoProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [repos, setRepos] = useState<RepoEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const pollIntervalsRef = useRef<
    Record<string, ReturnType<typeof setInterval>>
  >({});

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

  const startExtraction: RepoContextValue["startExtraction"] = async (
    url,
    append,
  ) => {
    const repo = repos.find((r) => r.url === url);
    if (!repo) return null;

    setRepos((prev) =>
      prev.map((r) =>
        r.url === url
          ? {
              ...r,
              status: "pending",
              message: "Queuing extraction...",
              progress: 0,
            }
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
            ? {
                ...r,
                taskId,
                status: "pending",
                message: "Extraction queued",
                progress: 0,
              }
            : r,
        ),
      );
      return taskId;
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ?? err?.message ?? "Extraction failed";
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
