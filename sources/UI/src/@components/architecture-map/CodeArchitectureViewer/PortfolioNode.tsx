import React, { memo } from "react";
import { Handle, Position } from "reactflow";

interface PortfolioNodeProps {
  data: {
    label: string;
    systemName?: string;
    repoUrl?: string | null;
    containersCount?: number;
    componentsCount?: number;
    completedAt?: string | null;
  };
}

const PortfolioNode: React.FC<PortfolioNodeProps> = memo(({ data }) => {
  const { label, systemName, containersCount = 0, componentsCount = 0 } = data;

  const repoShort = label.includes("/") ? label.split("/")[1] : label;
  const repoOwner = label.includes("/") ? label.split("/")[0] : "";

  return (
    <div className="portfolio-node">
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      <div className="portfolio-node__body">
        <div className="portfolio-node__name">
          {repoOwner && (
            <span className="portfolio-node__owner">{repoOwner}/</span>
          )}
          <span className="portfolio-node__repo">{repoShort}</span>
        </div>

        {systemName && systemName !== label && (
          <div className="portfolio-node__system">{systemName}</div>
        )}

        <div className="portfolio-node__meta">
          <span className="portfolio-node__pill">{containersCount} containers</span>
          <span className="portfolio-node__pill">{componentsCount} components</span>
        </div>

        <div className="portfolio-node__hint">zoom in to explore →</div>
      </div>
    </div>
  );
});

PortfolioNode.displayName = "PortfolioNode";
export default PortfolioNode;
