import React from 'react';
import BatchUrlInput from '../batchurlinput';
import GitHubOrgScanner from '../githuborgscanner';
import { codeArchitectureAPI } from '../../../../services/api';

const AVAILABLE_LEVELS = [
  'context_level',
  'container_level',
  'component_level',
];

interface FiltersSidebarProps {
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
  dependencyViewFilter: 'all' | 'business' | 'technical';
  setDependencyViewFilter: (val: 'all' | 'business' | 'technical') => void;

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
    options: { includeForks: boolean; maxRepos: number }
  ) => void;
  setArchitecture: (data: any) => void;
  setNodes: (nodes: any) => void;
  setEdges: (edges: any) => void;
  setExtractionStatus: (msg: string | null) => void;
  setExtractionError: (msg: string) => void;
  extractionStatus: string | null;
  extractionError: string | null;
}

export default function FiltersSidebar({
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
}: FiltersSidebarProps) {
  return (
    <aside className="filters-sidebar">
      {/* Search */}
      <div className="filter-section">
        <h3>Search</h3>
        <input
          type="text"
          placeholder="Search entities..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      {/* C4 Levels */}
      <div className="filter-section">
        <h3>C4 Levels</h3>
        {AVAILABLE_LEVELS.map(level => (
          <label key={level} className="checkbox-label">
            <input
              type="radio"
              name="c4-level"
              checked={selectedLevel === level}
              onChange={() => toggleLevel(level)}
            />
            <span>
              {level
                .replace('_', ' ')
                .replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          </label>
        ))}
      </div>

      {/* Relationship Types */}
      <div className="filter-section">
        <h3>Relationship Types</h3>
        <div className="checkbox-group">
          {relationshipTypes.map(type => (
            <label key={type} className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedRelationshipTypes.includes(type)}
                onChange={() => toggleRelationshipType(type)}
              />
              <span>{type}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Show External */}
      <div className="filter-section">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showExternal}
            onChange={e => setShowExternal(e.target.checked)}
          />
          <span>Show External Dependencies</span>
        </label>
      </div>

      {/* Dependency View Filter */}
      {selectedLevel === 'context_level' && showExternal && (
        <div className="filter-section">
          <h3>Dependency View</h3>
          <div className="radio-group">
            <label className="checkbox-label">
              <input
                type="radio"
                name="dependency-view"
                checked={dependencyViewFilter === 'business'}
                onChange={() => setDependencyViewFilter('business')}
              />
              <span>Context View (Business Systems)</span>
            </label>
            <label className="checkbox-label">
              <input
                type="radio"
                name="dependency-view"
                checked={dependencyViewFilter === 'technical'}
                onChange={() => setDependencyViewFilter('technical')}
              />
              <span>Container View (Technical Infra)</span>
            </label>
            <label className="checkbox-label">
              <input
                type="radio"
                name="dependency-view"
                checked={dependencyViewFilter === 'all'}
                onChange={() => setDependencyViewFilter('all')}
              />
              <span>Show All</span>
            </label>
          </div>
        </div>
      )}

      {/* Collapsible Add Repositories Section */}
      <div className="filter-section collapsible-section">
        <button
          className="section-toggle"
          onClick={() => setRepoSectionExpanded(!repoSectionExpanded)}
        >
          <h3>Add Repositories</h3>
          <span className={`toggle-icon ${repoSectionExpanded ? 'expanded' : ''}`}>
            ▼
          </span>
        </button>

        {repoSectionExpanded && (
          <div className="collapsible-content">
            {/* Single URL Quick Add */}
            <div className="quick-add-section">
              <input
                type="text"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onChange={e => setGithubUrl(e.target.value)}
                className="search-input"
                onKeyPress={e => e.key === 'Enter' && handleExtractFromGithub()}
              />
              <button
                className="fit-button"
                onClick={handleExtractFromGithub}
                disabled={isExtracting}
              >
                {isExtracting ? 'Extracting...' : 'Add Repository'}
              </button>
            </div>

            {/* Local folder scan */}
            <div className="quick-add-section">
              <input
                type="text"
                placeholder="/cms  or  /cms/my-service"
                value={localPath}
                onChange={e => setLocalPath(e.target.value)}
                className="search-input"
                onKeyPress={e => e.key === 'Enter' && handleScanLocalPath()}
              />
              <button
                className="fit-button"
                onClick={handleScanLocalPath}
                disabled={isExtracting || !localPath.trim()}
                title="Scan a local folder mounted inside the container"
              >
                {isExtracting ? 'Scanning...' : 'Scan Local Folder'}
              </button>
            </div>

            {/* Batch URL Input */}
            <div className="batch-section">
              <h4 className="subsection-title">Batch Input</h4>
              <BatchUrlInput
                onBatchExtract={handleBatchExtract}
                isExtracting={isExtracting}
              />
            </div>

            {/* GitHub Organization Scanner */}
            <div className="org-scan-section">
              <h4 className="subsection-title">GitHub Account/Org</h4>
              <GitHubOrgScanner
                onScanStart={handleGitHubOrgScan}
                isScanning={isExtracting}
              />
            </div>

            {/* Clear All Button */}
            <button
              className="reset-button"
              onClick={async () => {
                if (
                  confirm(
                    '⚠️ Clear ALL repositories and start fresh? This will remove all accumulated architecture data.'
                  )
                ) {
                  try {
                    await codeArchitectureAPI.clearArchitecture();
                    setArchitecture(null);
                    setNodes([]);
                    setEdges([]);
                    setGithubUrl('');
                    setExtractionStatus(
                      'All repositories cleared - ready for fresh extraction'
                    );
                    setExtractionError('');
                  } catch (err) {
                    setExtractionError('Failed to clear data');
                  }
                }
              }}
              disabled={isExtracting}
              title="Clear all repositories and start fresh"
            >
              Clear All
            </button>

            {/* Status messages */}
            {extractionStatus && (
              <div className="extract-status">{extractionStatus}</div>
            )}
            {extractionError && (
              <div className="extract-error">{extractionError}</div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
