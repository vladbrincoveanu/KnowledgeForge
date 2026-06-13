import React from "react";

interface MetricsBarProps {
  // View mode
  viewMode: "diagram" | "data";
  setViewMode: (mode: "diagram" | "data") => void;

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
  viewMode,
  setViewMode,
  searchTerm,
  setSearchTerm,
  selectedLevel,
  toggleLevel,
  relationshipTypes,
  selectedRelationshipTypes,
  toggleRelationshipType,
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
        <div className="view-mode-toggle">
          <button
            className={`view-mode-btn cursor-pointer ${viewMode === "diagram" ? "active" : ""}`}
            onClick={() => setViewMode("diagram")}
          >
            Diagram
          </button>
          <button
            className={`view-mode-btn cursor-pointer ${viewMode === "data" ? "active" : ""}`}
            onClick={() => setViewMode("data")}
          >
            Data
          </button>
        </div>

        <div className="search-section">
          <input
            type="text"
            placeholder="Find a node, service, or file..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="metrics-filters-group">
          <div className="metrics-cluster levels-section">
            <span className="section-label">Level</span>
            <div className="level-pills">
              {AVAILABLE_LEVELS.map((level) => (
                <button
                  key={level.key}
                  className={`level-pill cursor-pointer ${selectedLevel === level.key ? "active" : ""}`}
                  onClick={() => toggleLevel(level.key)}
                >
                  {level.label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
