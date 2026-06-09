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
import { useRepos, RepoStatus } from "../RepoProvider/RepoProvider";
import "./RepoExplorer.scss";

interface RepoExplorerProps {
  onExtractionStarted?: (
    taskId: string,
    file: { name: string; type: string; size: number },
  ) => void;
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
  const {
    repos,
    isExtracting,
    removeRepo,
    clearAll,
    startExtraction,
    addRepo,
  } = useRepos();
  const [appendMode, setAppendMode] = useState(false);
  const [isUrlDragging, setIsUrlDragging] = useState(false);

  const idleCount = repos.filter(
    (r) => r.status === "idle" || r.status === "failed",
  ).length;

  const extractAll = async () => {
    const idleRepos = repos.filter(
      (r) => r.status === "idle" || r.status === "failed",
    );
    const append = appendMode;
    for (const repo of idleRepos) {
      const taskId = await startExtraction(repo.url, append);
      if (taskId && onExtractionStarted) {
        onExtractionStarted(taskId, {
          name: repo.url,
          type: "github",
          size: 0,
        });
      }
    }
  };

  const handleUrlDragOver = (e: React.DragEvent) => {
    // Only react if a URL/text payload is being dragged, not files
    if (e.dataTransfer.types.includes("text/plain")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      setIsUrlDragging(true);
    }
  };

  const handleUrlDragLeave = (e: React.DragEvent) => {
    if (e.currentTarget === e.target) setIsUrlDragging(false);
  };

  const handleUrlDrop = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes("text/plain")) return;
    e.preventDefault();
    setIsUrlDragging(false);
    const text = e.dataTransfer.getData("text/plain").trim();
    if (!text) return;
    // Accept the first whitespace-delimited token that looks like a URL.
    const tokens = text.split(/\s+/);
    let added = 0;
    let lastError = "";
    for (const token of tokens) {
      let url: URL;
      try {
        url = new URL(token);
      } catch {
        continue;
      }
      if (url.protocol !== "https:" && url.protocol !== "http:") continue;
      const result = addRepo(url.toString());
      if (result.ok) added += 1;
      else lastError = result.error;
    }
    if (added === 0 && lastError) {
      // Surface only the last validation error; the drop event has no
      // native channel for it.
      // eslint-disable-next-line no-console
      console.warn("Drop ignored:", lastError);
    }
  };

  return (
    <div
      className={`repo-explorer${isUrlDragging ? " repo-explorer--url-drop" : ""}`}
      onDragOver={handleUrlDragOver}
      onDragLeave={handleUrlDragLeave}
      onDrop={handleUrlDrop}
    >
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
            Each repo will be cloned, scanned, and added to the architecture
            graph
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
