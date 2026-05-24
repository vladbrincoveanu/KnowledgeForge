import React from "react";

interface ArchitectureHeaderProps {
  nodeCount: number;
  edgeCount: number;
  avgConnections: string;
}

export default function ArchitectureHeader({
  nodeCount,
  edgeCount,
  avgConnections,
}: ArchitectureHeaderProps) {
  return (
    <div className="viewer-header">
      <div className="header-content">
        <h2>Architecture Context</h2>
      </div>
      <div className="header-stats">
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
