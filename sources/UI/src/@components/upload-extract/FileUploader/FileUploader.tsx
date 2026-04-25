import React, { useState, useEffect, useCallback } from "react";
import { codeArchitectureAPI, wsService } from "@/services/api";
import { UploadedFile } from "@/types";
import {
  Github,
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
} from "lucide-react";
import "./FileUploader.scss";

interface FileUploaderProps {
  onFilesUploaded: (files: UploadedFile[]) => void;
  isProcessing: boolean;
  onExtractionStarted: (taskId: string, file: UploadedFile) => void;
  showNotification: (
    message: string,
    type: "success" | "error" | "info",
  ) => void;
}

type RepoStatus = "idle" | "pending" | "scanning" | "completed" | "failed";

interface RepoEntry {
  url: string;
  taskId?: string;
  status: RepoStatus;
  message: string;
  progress: number;
  containersCount: number;
  componentsCount: number;
  error?: string;
}

const isValidGitHubUrl = (url: string): boolean => {
  try {
    const u = new URL(url);
    return (
      (u.hostname === "github.com" || u.hostname === "www.github.com") &&
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
  const [inputError, setInputError] = useState("");
  const [repos, setRepos] = useState<RepoEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
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
      setInputError("Please enter a GitHub URL.");
      return;
    }
    if (!isValidGitHubUrl(trimmed)) {
      setInputError(
        "Enter a valid GitHub repository URL (e.g. https://github.com/owner/repo).",
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
        status: "idle",
        message: "Ready to extract",
        progress: 0,
        containersCount: 0,
        componentsCount: 0,
      },
    ]);
    setInputUrl("");
  };

  const removeRepo = (url: string) => {
    setRepos((prev) => prev.filter((r) => r.url !== url));
  };

  const clearAll = () => {
    Object.values(pollIntervalsRef.current).forEach(clearInterval);
    pollIntervalsRef.current = {};
    setRepos([]);
    setInputUrl("");
    setInputError("");
  };

  const pollStatus = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const raw = (await codeArchitectureAPI.getExtractionStatus(
          taskId,
        )) as any;
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
        clearInterval(interval);
        delete pollIntervalsRef.current[taskId];
      }
    }, 2000);
    pollIntervalsRef.current[taskId] = interval;
  };

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
      setRepos((prev) =>
        prev.map((r) =>
          r.url === repo.url
            ? { ...r, status: "pending", message: "Queuing extraction..." }
            : r,
        ),
      );

      try {
        const result = await codeArchitectureAPI.extractFromGitHub(
          repo.url,
          true,
          true,
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

        // Notify parent with a synthetic file record so activeTaskId is tracked
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
  };

  const idleCount = repos.filter(
    (r) => r.status === "idle" || r.status === "failed",
  ).length;

  return (
    <div className="repo-extractor">
      {/* URL Input */}
      <div className="url-input-section">
        <div className="url-input-row">
          <div className="url-input-wrapper">
            <Github size={18} className="url-input-icon" />
            <input
              type="url"
              className={`url-input ${inputError ? "url-input--error" : ""}`}
              placeholder="https://github.com/owner/repository"
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
        {inputError && <p className="url-error">{inputError}</p>}
      </div>

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
                  <Github size={16} className="repo-item__icon" />
                  <div className="repo-item__info">
                    <span className="repo-item__url">{repo.url}</span>
                    <span className="repo-item__message">{repo.message}</span>
                    {repo.status === "scanning" && (
                      <div className="repo-item__progress">
                        <div
                          className="repo-item__progress-fill"
                          style={{
                            width: `${Math.round(repo.progress * 100)}%`,
                          }}
                        />
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
          <p>Add one or more GitHub repository URLs above</p>
          <p className="empty-state__hint">
            Each repo will be cloned, scanned, and added to the architecture
            graph
          </p>
        </div>
      )}

      {/* Actions */}
      {repos.length > 0 && (
        <div className="repo-actions">
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
