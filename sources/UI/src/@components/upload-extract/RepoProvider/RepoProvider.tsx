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
