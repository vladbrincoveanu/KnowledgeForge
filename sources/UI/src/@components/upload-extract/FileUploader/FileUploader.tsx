import React, { useState, useEffect, useCallback } from "react";
import { codeArchitectureAPI, wsService } from "@/services/api";
import { UploadedFile } from "@/types";
import {
  Github,
  Folder,
  Plus,
  X,
  Play,
  Trash2,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader,
  Package,
  Layers,
  Lock,
  Eye,
  EyeOff,
  RotateCcw,
} from "lucide-react";
import "./FileUploader.scss";
import FolderDropZone from "./FolderDropZone";

interface FileUploaderProps {
  onFilesUploaded: (files: UploadedFile[]) => void;
  isProcessing: boolean;
  onExtractionStarted: (taskId: string, file: UploadedFile) => void;
  showNotification: (
    message: string,
    type: "success" | "error" | "info",
  ) => void;
}

type RepoStatus = "idle" | "pending" | "scanning" | "completed" | "failed" | "zipping" | "uploading";

interface RepoEntry {
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

const FileUploader: React.FC<FileUploaderProps> = ({
  onExtractionStarted,
  showNotification,
}) => {
  const [inputUrl, setInputUrl] = useState("");
  const [inputToken, setInputToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [appendMode, setAppendMode] = useState(false);
  const [inputError, setInputError] = useState("");
  const [repos, setRepos] = useState<RepoEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [activeTab, setActiveTab] = useState<"github" | "local">("github");
  const pollIntervalsRef = React.useRef<
    Record<string, ReturnType<typeof setInterval>>
  >({});

  const handleWebSocketMessage = useCallback((data?: unknown) => {
    const wsData = data as {
      task_id?: string;
      status?: string;
      message?: string;
      progress?: number;
    };
    if (!wsData?.task_id) return;

    setRepos((prev) =>
      prev.map((r) => {
        if (r.taskId !== wsData.task_id) return r;
        return {
          ...r,
          status: (wsData.status as RepoStatus) ?? r.status,
          message: wsData.message ?? r.message,
          progress: wsData.progress ?? r.progress,
        };
      }),
    );
  }, []);

  useEffect(() => {
    wsService.connect();
    wsService.on("message", handleWebSocketMessage);
    return () => {
      wsService.off("message", handleWebSocketMessage);
      Object.values(pollIntervalsRef.current).forEach(clearInterval);
    };
  }, [handleWebSocketMessage]);

  const addRepo = () => {
    const trimmed = inputUrl
      .trim()
      .replace(/\.git\/?$/, "")
      .replace(/\/$/, "");
    if (!trimmed) {
      setInputError("Please enter a repository URL.");
      return;
    }
    if (!isValidGitUrl(trimmed)) {
      setInputError(
        "Enter a valid repository URL (e.g. https://github.com/owner/repo or https://gitlab.example.com/group/repo).",
      );
      return;
    }
    if (repos.some((r) => r.url === trimmed)) {
      setInputError("This repository has already been added.");
      return;
    }
    setInputError("");
    setRepos((prev) => [
      ...prev,
      {
        url: trimmed,
        token: inputToken.trim() || undefined,
        status: "idle",
        message: "Ready to extract",
        progress: 0,
        containersCount: 0,
        componentsCount: 0,
      },
    ]);
    setInputUrl("");
    setInputToken("");
  };

  const removeRepo = (url: string) => {
    setRepos((prev) => prev.filter((r) => r.url !== url));
  };

  const clearAll = () => {
    Object.values(pollIntervalsRef.current).forEach(clearInterval);
    pollIntervalsRef.current = {};
    setRepos([]);
    setInputUrl("");
    setInputToken("");
    setInputError("");
  };

  const pollStatus = (taskId: string) => {
    let consecutiveErrors = 0;
    const interval = setInterval(async () => {
      try {
        const raw = (await codeArchitectureAPI.getExtractionStatus(
          taskId,
        )) as any;
        consecutiveErrors = 0;
        const rawStatus: string = raw.status ?? "pending";
        const newStatus: RepoStatus =
          rawStatus === "scanning"
            ? "scanning"
            : rawStatus === "completed"
              ? "completed"
              : rawStatus === "failed"
                ? "failed"
                : rawStatus === "pending"
                  ? "pending"
                  : "pending";
        setRepos((prev) =>
          prev.map((r) => {
            if (r.taskId !== taskId) return r;
            return {
              ...r,
              status: newStatus,
              message: raw.message ?? r.message,
              progress: raw.progress ?? r.progress,
              containersCount: raw.containers_count ?? r.containersCount,
              componentsCount: raw.components_count ?? r.componentsCount,
            };
          }),
        );
        if (rawStatus === "completed" || rawStatus === "failed") {
          clearInterval(interval);
          delete pollIntervalsRef.current[taskId];
        }
      } catch {
        consecutiveErrors++;
        // Stop only after 10 consecutive failures (~20s of no response).
        // Transient errors (server busy during extraction) should not kill the poll.
        if (consecutiveErrors >= 10) {
          clearInterval(interval);
          delete pollIntervalsRef.current[taskId];
        }
      }
    }, 2000);
    pollIntervalsRef.current[taskId] = interval;
  };

  const extractRepo = async (repo: RepoEntry, append: boolean) => {
    setRepos((prev) =>
      prev.map((r) =>
        r.url === repo.url
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
        repo.url,
        true,
        append,
        repo.token,
      );
      const taskId = result.task_id;
      setRepos((prev) =>
        prev.map((r) =>
          r.url === repo.url
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
      onExtractionStarted(taskId, {
        name: repo.url,
        headers: [],
        data: [],
        size: 0,
        rowCount: 0,
        type: "github",
      });
      pollStatus(taskId);
      showNotification(`Extraction started for ${repo.url}`, "success");
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ?? err?.message ?? "Extraction failed";
      setRepos((prev) =>
        prev.map((r) =>
          r.url === repo.url ? { ...r, status: "failed", message: msg } : r,
        ),
      );
      showNotification(
        `Failed to start extraction for ${repo.url}: ${msg}`,
        "error",
      );
    }
  };

  const uploadZip = useCallback(
    (blob: Blob, folderName: string): Promise<{ task_id: string }> =>
      new Promise((resolve, reject) => {
        const form = new FormData();
        form.append("file", blob, `${folderName}.zip`);
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/v1/code/upload-repo");
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            setRepos((prev) =>
              prev.map((r) =>
                r.url === folderName + "/"
                  ? { ...r, status: "uploading" as RepoStatus, message: `Uploading… ${pct}%`, progress: pct / 100 }
                  : r,
              ),
            );
          }
        };
        xhr.onload = () => {
          if (xhr.status === 202) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            reject(new Error(xhr.responseText || "Upload failed"));
          }
        };
        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(form);
      }),
    [],
  );

  const handleFolderZipReady = useCallback(
    async (blob: Blob, name: string, sizeBytes: number) => {
      const displayName = name + "/";
      if (repos.some((r) => r.url === displayName)) {
        showNotification("This folder has already been added.", "info");
        return;
      }
      setRepos((prev) => [
        ...prev,
        {
          url: displayName,
          status: "uploading" as RepoStatus,
          message: "Uploading…",
          progress: 0,
          containersCount: 0,
          componentsCount: 0,
        },
      ]);
      try {
        const result = await uploadZip(blob, name);
        const taskId = result.task_id;
        setRepos((prev) =>
          prev.map((r) =>
            r.url === displayName
              ? { ...r, taskId, status: "pending" as RepoStatus, message: "Queued", progress: 0 }
              : r,
          ),
        );
        onExtractionStarted(taskId, {
          name: displayName,
          headers: [],
          data: [],
          size: sizeBytes,
          rowCount: 0,
          type: "local",
        });
        pollStatus(taskId);
        showNotification(`Extraction started for ${displayName}`, "success");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setRepos((prev) =>
          prev.map((r) =>
            r.url === displayName
              ? { ...r, status: "failed" as RepoStatus, message: msg }
              : r,
          ),
        );
        showNotification(`Upload failed for ${displayName}: ${msg}`, "error");
      }
    },
    [repos, showNotification, uploadZip, pollStatus, onExtractionStarted],
  );

  const handleFolderProgress = useCallback(
    (phase: "zipping" | "uploading" | "warning", value: number) => {
      if (phase === "warning") {
        const mb = Math.round(value / 1024 / 1024);
        showNotification(
          `Large zip (${mb} MB) — upload may be slow.`,
          "info",
        );
        return;
      }
      setRepos((prev) =>
        prev.map((r) =>
          r.status === "zipping"
            ? {
                ...r,
                message: `Zipping… ${value}%`,
                progress: value / 100,
              }
            : r,
        ),
      );
    },
    [showNotification],
  );

  const extractAll = async () => {
    const idleRepos = repos.filter(
      (r) => r.status === "idle" || r.status === "failed",
    );
    if (idleRepos.length === 0) {
      showNotification("No repositories to extract.", "info");
      return;
    }

    setIsExtracting(true);

    for (const repo of idleRepos) {
      await extractRepo(repo, appendMode);
    }

    setIsExtracting(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") addRepo();
  };

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

  const idleCount = repos.filter(
    (r) => r.status === "idle" || r.status === "failed",
  ).length;

  return (
    <div className="repo-extractor">
      {/* Tabs */}
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
      <>
      {/* URL Input */}
      <div className="url-input-section">
        <div className="url-input-row">
          <div className="url-input-wrapper">
            <Github size={18} className="url-input-icon" />
            <input
              type="url"
              className={`url-input ${inputError ? "url-input--error" : ""}`}
              placeholder="https://github.com/owner/repo or https://gitlab.example.com/group/repo"
              value={inputUrl}
              onChange={(e) => {
                setInputUrl(e.target.value);
                if (inputError) setInputError("");
              }}
              onKeyDown={handleKeyDown}
            />
          </div>
          <button className="btn-add" onClick={addRepo}>
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
        {inputError && <p className="url-error">{inputError}</p>}
      </div>
      </>
      )}

      {/* Repo List */}
      {repos.length > 0 && (
        <div className="repo-list">
          {repos.map((repo) => {
            const cfg = statusConfig[repo.status];
            return (
              <div
                key={repo.url}
                className={`repo-item repo-item--${repo.status}`}
              >
                <div className="repo-item__left">
                  {repo.url.endsWith("/") ? (
                    <Folder size={16} className="repo-item__icon" />
                  ) : (
                    <Github size={16} className="repo-item__icon" />
                  )}
                  <div className="repo-item__info">
                    <span className="repo-item__url">
                      {repo.url}
                      {repo.token && (
                        <Lock
                          size={12}
                          className="repo-item__lock"
                          title="Using access token"
                        />
                      )}
                    </span>
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
                            style={{
                              width: `${Math.round(repo.progress * 100)}%`,
                            }}
                          />
                        )}
                      </div>
                    )}
                    {repo.status === "completed" && (
                      <div className="repo-item__stats">
                        <span>
                          <Package size={12} /> {repo.containersCount}{" "}
                          containers
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
                      onClick={() => extractRepo(repo, appendMode)}
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

      {/* Empty state */}
      {repos.length === 0 && (
        <div className="empty-state">
          <Github size={48} className="empty-state__icon" />
          <p>Add one or more repository URLs above</p>
          <p className="empty-state__hint">
            Each repo will be cloned, scanned, and added to the architecture
            graph
          </p>
        </div>
      )}

      {/* Actions */}
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

export default FileUploader;
