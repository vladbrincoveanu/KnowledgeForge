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
      <div className="metrics-row metrics-row-single">
        <div className="metrics-section search-section">
          <input
            type="text"
            placeholder="Find a node, service, or file..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="metrics-cluster levels-section">
          <span className="section-label">Level</span>
          <div className="level-pills">
            {AVAILABLE_LEVELS.map((level) => (
              <button
                key={level.key}
                className={`level-pill cursor-pointer ${selectedLevel === level.key ? "active" : ""}`}
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
              className={`view-btn cursor-pointer ${dependencyViewFilter === "all" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("all")}
            >
              All
            </button>
            <button
              className={`view-btn cursor-pointer ${dependencyViewFilter === "business" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("business")}
            >
              Business
            </button>
            <button
              className={`view-btn cursor-pointer ${dependencyViewFilter === "technical" ? "active" : ""}`}
              onClick={() => setDependencyViewFilter("technical")}
            >
              Technical
            </button>
          </div>
        </div>

        <div className="metrics-cluster external-section">
          <span className="section-label">Scope</span>
          <label className="toggle-label cursor-pointer">
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
    </div>
  );
}
