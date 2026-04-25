import React from "react";
// Use reactflow (v11) - not @xyflow/react
import { Handle, Position } from "reactflow";

interface ContainerNodeProps {
  data: {
    label: string;
    containerType?: string;
    technology?: string;
  };
}

/**
 * Map container_type values to a visual category.
 * Categories drive the badge label, badge color, and node border.
 */
type ContainerCategory = "database" | "broker" | "cache" | "service";

const CATEGORY_CONFIG: Record<
  ContainerCategory,
  { badge: string; color: string; border: string }
> = {
  database: { badge: "DATABASE", color: "#1d4ed8", border: "#3b82f6" },
  broker: { badge: "MESSAGE BROKER", color: "#b45309", border: "#f59e0b" },
  cache: { badge: "CACHE", color: "#047857", border: "#10b981" },
  service: { badge: "CONTAINER", color: "#334155", border: "#94a3b8" },
};

function inferCategory(containerType?: string): ContainerCategory {
  if (!containerType) return "service";
  const lower = containerType.toLowerCase();
  if (
    lower.includes("database") ||
    lower.includes("data store") ||
    lower.includes("datastore")
  )
    return "database";
  if (
    lower.includes("message broker") ||
    lower.includes("event bus") ||
    lower.includes("queue")
  )
    return "broker";
  if (lower.includes("cache") || lower.includes("in-memory")) return "cache";
  return "service";
}

const ContainerNode: React.FC<ContainerNodeProps> = ({ data }) => {
  // Cluster frames (e.g., Kubernetes Cluster) use a minimal rendering — no badge
  const isClusterFrame = data.containerType === "Runtime Environment";
  if (isClusterFrame) {
    return (
      <div className="container-node">
        <div className="container-header">
          <div className="container-label">{data.label}</div>
          {data.technology && (
            <div className="container-tech">{data.technology}</div>
          )}
        </div>
      </div>
    );
  }

  const category = inferCategory(data.containerType);
  const config = CATEGORY_CONFIG[category];

  return (
    <div
      className={`container-node container-node--${category}`}
      style={{ borderColor: config.border }}
    >
      <Handle type="target" position={Position.Left} />
      <div
        className="container-badge"
        style={{ backgroundColor: config.color }}
      >
        {config.badge}
      </div>
      <div className="container-header">
        <div className="container-label">{data.label}</div>
        {data.technology && (
          <div className="container-tech">{data.technology}</div>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
};

export default ContainerNode;
