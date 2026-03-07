import React from "react";

interface MetricsBarProps {
  // Search
  searchTerm: string;
  setSearchTerm: (val: string) => void;

  // C4 level
  selectedLevel: string;
  toggleLevel: (level: string) => void;

  // Relationship types
  relationshipTypes: string[];
  selectedRelationshipTypes: string[];
  toggleRelationshipType: (type: string) => void;

  // Externals + dependency view
  showExternal: boolean;
  setShowExternal: (val: boolean) => void;
  dependencyViewFilter: "all" | "business" | "technical";
  setDependencyViewFilter: (val: "all" | "business" | "technical") => void;

  // Repo section
  repoSectionExpanded: boolean;
  setRepoSectionExpanded: (val: boolean) => void;
  githubUrl: string;
  setGithubUrl: (val: string) => void;
  localPath: string;
  setLocalPath: (val: string) => void;
  isExtracting: boolean;
  handleExtractFromGithub: () => void;
  handleScanLocalPath: () => void;
  handleBatchExtract: (urls: string[]) => void;
  handleGitHubOrgScan: (
    username: string,
    options: { includeForks: boolean; maxRepos: number },
  ) => void;
  setArchitecture: (data: any) => void;
  setNodes: (nodes: any) => void;
  setEdges: (edges: any) => void;
  setExtractionStatus: (msg: string | null) => void;
  setExtractionError: (msg: string) => void;
  extractionStatus: string | null;
  extractionError: string | null;
}

const AVAILABLE_LEVELS = [
  { key: "context_level", label: "Context", color: "#8b5cf6" },
  { key: "container_level", label: "Container", color: "#06b6d4" },
  { key: "component_level", label: "Component", color: "#10b981" },
  { key: "code_level", label: "Code", color: "#f59e0b" },
];

export default function MetricsBar({
  searchTerm,
  setSearchTerm,
  selectedLevel,
  toggleLevel,
  relationshipTypes,
  selectedRelationshipTypes,
  toggleRelationshipType,
  showExternal,
  setShowExternal,
  dependencyViewFilter,
  setDependencyViewFilter,
  repoSectionExpanded,
  setRepoSectionExpanded,
  githubUrl,
  setGithubUrl,
  localPath,
  setLocalPath,
  isExtracting,
  handleExtractFromGithub,
  handleScanLocalPath,
  handleBatchExtract,
  handleGitHubOrgScan,
  setArchitecture,
  setNodes,
  setEdges,
  setExtractionStatus,
  setExtractionError,
  extractionStatus,
  extractionError,
}: MetricsBarProps) {
  return (
    <div className="metrics-bar">
      <div className="metrics-row metrics-row-primary">
        <div className="metrics-section search-section">
          <input
            type="text"
            placeholder="Find a node, service, or file..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="metrics-actions">
          <div className="metrics-section extract-section">
            <button
              className="extract-btn"
              onClick={() => setRepoSectionExpanded(!repoSectionExpanded)}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
              Add Repository
            </button>
          </div>
        </div>
      </div>

      <div className="metrics-row metrics-row-secondary">
        <div className="metrics-cluster levels-section">
          <span className="section-label">Level</span>
          <div className="level-pills">
            {AVAILABLE_LEVELS.map((level) => (
              <button
                key={level.key}
                className={`level-pill ${selectedLevel === level.key ? "active" : ""}`}
                onClick={() => toggleLevel(level.key)}
                style={
                  {
                    "--pill-color": level.color,
                  } as React.CSSProperties
                }
              >
                {level.label}
              </button>
            ))}
          </div>
        </div>

        <div className="metrics-cluster dependency-section">
          <span className="section-label">View</span>
          <div className="view-toggle">
            <button
              className={`view-btn ${dependencyViewFilter === "all" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("all")}
            >
              All
            </button>
            <button
              className={`view-btn ${dependencyViewFilter === "business" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("business")}
            >
              Business
            </button>
            <button
              className={`view-btn ${dependencyViewFilter === "technical" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("technical")}
            >
              Technical
            </button>
          </div>
        </div>

        <div className="metrics-cluster external-section">
          <span className="section-label">Scope</span>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={showExternal}
              onChange={(e) => setShowExternal(e.target.checked)}
            />
            <span className="toggle-switch"></span>
            <span>External</span>
          </label>
        </div>
      </div>

      {/* Repository Panel (expandable) */}
      {repoSectionExpanded && (
        <div className="repo-panel">
          <div className="repo-panel-header">
            <h4>Add Repository</h4>
            <button
              className="close-btn"
              onClick={() => setRepoSectionExpanded(false)}
            >
              ×
            </button>
          </div>
          <div className="repo-panel-content">
            <div className="input-group">
              <label>GitHub URL</label>
              <div className="input-row">
                <input
                  type="text"
                  placeholder="https://github.com/owner/repo"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                />
                <button
                  onClick={handleExtractFromGithub}
                  disabled={isExtracting || !githubUrl}
                >
                  {isExtracting ? "Extracting..." : "Extract"}
                </button>
              </div>
            </div>
            {extractionStatus && (
              <div className="status-message">{extractionStatus}</div>
            )}
            {extractionError && (
              <div className="error-message">{extractionError}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
