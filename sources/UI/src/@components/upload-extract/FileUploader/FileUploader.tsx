import React, { useState, useCallback } from "react";
import { Github, Plus, Lock, Eye, EyeOff } from "lucide-react";
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
  isProcessing: _isProcessing,
  onExtractionStarted: _onExtractionStarted,
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
    async (_blob: Blob, name: string, _sizeBytes: number) => {
      const displayName = name + "/";
      const result = addRepo(displayName);
      if (!result.ok) {
        showNotification(result.error, "error");
        return;
      }
      showNotification(
        `Folder "${name}" added to queue. Use Extract All to start.`,
        "info",
      );
    },
    [addRepo, showNotification],
  );

  const handleFolderProgress = useCallback(() => {
    // Folder upload XHR deferred — see RepoExplorer.startExtraction for the GitHub path.
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
