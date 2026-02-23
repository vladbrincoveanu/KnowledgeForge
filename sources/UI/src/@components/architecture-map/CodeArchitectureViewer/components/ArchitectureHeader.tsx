import React from 'react';

interface ArchitectureHeaderProps {
  nodeCount: number;
  edgeCount: number;
  avgConnections: string;
  onExportStructurizr?: () => void;
  onExportMermaid?: () => void;
}

export default function ArchitectureHeader({
  nodeCount,
  edgeCount,
  avgConnections,
  onExportStructurizr,
  onExportMermaid,
}: ArchitectureHeaderProps) {
  return (
    <div className="viewer-header">
      <div className="header-content">
        <h2>Architecture Context (Multi-Repository)</h2>
        <p>
          Cumulative view of all added repositories - add multiple projects to
          see complete landscape
        </p>
      </div>
      <div className="header-stats">
        <div className="header-actions">
          <button
            type="button"
            className="header-action-btn"
            onClick={onExportStructurizr}
            disabled={!onExportStructurizr}
          >
            Export Structurizr
          </button>
          <button
            type="button"
            className="header-action-btn"
            onClick={onExportMermaid}
            disabled={!onExportMermaid}
          >
            Export Mermaid
          </button>
        </div>
        <div className="header-stat">
          <span className="header-stat-value">{nodeCount}</span>
          <span className="header-stat-label">Entities</span>
        </div>
        <div className="header-stat">
          <span className="header-stat-value">{edgeCount}</span>
          <span className="header-stat-label">Relationships</span>
        </div>
        <div className="header-stat">
          <span className="header-stat-value">{avgConnections}</span>
          <span className="header-stat-label">Avg Connections</span>
        </div>
      </div>
    </div>
  );
}
