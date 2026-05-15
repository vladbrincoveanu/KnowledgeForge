import React, { memo } from "react";
import { Handle, Position } from "reactflow";
import { EnrichmentBadge } from "../../../../components/CodeArchitectureViewer/EnrichmentBadge";

interface ContainerMeta {
  container_type?: string;
  technology?: string;
  protocol?: string;
  runtime_environment?: string;
  deployment?: string;
  [key: string]: any;
}

interface CustomNodeProps {
  data: {
    label: string;
    type: string;
    displayType: string;
    fullName?: string;
    file?: string;
    line?: number;
    isExternal?: boolean;
    decorators?: string[];
    containerMeta?: ContainerMeta;
    decision_mode?: string;
  };
}

const EXTERNAL_TYPES = new Set([
  "external_system",
  "external_service",
  "messaging",
  "cache",
  "database",
  "logging",
]);

interface C4Style {
  bg: string;
  color: string;
  stereotype: string | null;
  isC4: boolean;
}

const getC4Style = (type: string): C4Style => {
  if (type === "system") {
    return {
      bg: "#1168bd",
      color: "white",
      stereotype: "«system»",
      isC4: true,
    };
  }
  if (type === "person") {
    return {
      bg: "#08427b",
      color: "white",
      stereotype: "«person»",
      isC4: true,
    };
  }
  if (EXTERNAL_TYPES.has(type)) {
    return {
      bg: "#999999",
      color: "white",
      stereotype: "«external system»",
      isC4: true,
    };
  }
  return { bg: "", color: "", stereotype: null, isC4: false };
};

/**
 * Infer a visual category from the container_type string.
 */
type ContainerCategory = "database" | "broker" | "cache" | "service";

interface CategoryStyle {
  headerBg: string;
  headerLabel: string;
  borderColor: string;
  bodyBg: string;
}

const CATEGORY_STYLES: Record<ContainerCategory, CategoryStyle> = {
  database: {
    headerBg: "#1d4ed8",
    headerLabel: "DATABASE",
    borderColor: "#3b82f6",
    bodyBg: "#eff6ff",
  },
  broker: {
    headerBg: "#b45309",
    headerLabel: "MESSAGE BROKER",
    borderColor: "#f59e0b",
    bodyBg: "#fffbeb",
  },
  cache: {
    headerBg: "#047857",
    headerLabel: "CACHE",
    borderColor: "#10b981",
    bodyBg: "#ecfdf5",
  },
  service: {
    headerBg: "#334155",
    headerLabel: "CONTAINER",
    borderColor: "#94a3b8",
    bodyBg: "#ffffff",
  },
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

const CustomNode: React.FC<CustomNodeProps> = ({ data }) => {
  // Format the label to be more readable (replace underscores, limit length)
  const formatLabel = (label: string) => {
    const formatted = label.replace(/_/g, " ");
    return formatted.length > 30
      ? formatted.substring(0, 27) + "..."
      : formatted;
  };

  const isContainer = data.type === "container";
  const { bg, color, stereotype, isC4 } = getC4Style(data.type);
  const isGhostExternal = data.attributes?.isGhostExternal === true;

  const ghostStyle = isGhostExternal
    ? { border: "2px dashed #9ca3af", background: "#f9fafb", opacity: 0.9 }
    : undefined;

  // For container entities, use category-based styling
  if (isContainer && data.containerMeta) {
    const category = inferCategory(data.containerMeta.container_type);
    const catStyle = CATEGORY_STYLES[category];
    const tech = data.containerMeta.technology;

    return (
      <div
        className={`react-flow__node-custom node-type-container${
          isGhostExternal ? " node-external-ghost" : ""
        }`}
        style={{
          borderColor: catStyle.borderColor,
          ...ghostStyle,
        }}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="custom-handle"
        />

        <div
          className="node-header"
          style={{ background: catStyle.headerBg, color: "#fff" }}
        >
          {catStyle.headerLabel}
        </div>

        <div className="node-content">
          <div className="node-name" title={data.label}>
            {formatLabel(data.label)}
          </div>
          {data.file && <div className="node-file">{data.file}</div>}
          {tech && (
            <div className="node-file" style={{ color: "#64748b" }}>
              {tech}
            </div>
          )}
        </div>

        <Handle
          type="source"
          position={Position.Right}
          className="custom-handle"
        />
      </div>
    );
  }

  return (
    <div
      className={`react-flow__node-custom node-type-${data.type}${
        isGhostExternal ? " node-external-ghost" : ""
      }`}
      style={
        isC4
          ? { background: bg, color, borderColor: bg, ...ghostStyle }
          : ghostStyle
      }
    >
      <Handle
        type="target"
        position={isContainer ? Position.Left : Position.Top}
        className="custom-handle"
      />

      {stereotype ? (
        <div
          className="node-stereotype"
          style={{
            fontSize: 10,
            opacity: 0.85,
            marginBottom: 2,
            textAlign: "center",
          }}
        >
          {data.type === "person" && <span style={{ marginRight: 4 }}>👤</span>}
          {stereotype}
        </div>
      ) : (
        <div className="node-header">{data.displayType}</div>
      )}

      <div className="node-content">
        <div className="node-name" title={data.label}>
          {formatLabel(data.label)}
          <EnrichmentBadge decisionMode={data.decision_mode} />
        </div>
        {data.isExternal && (
          <div className="node-badge external-badge">External</div>
        )}
        {data.file && <div className="node-file">{data.file}</div>}
      </div>

      <Handle
        type="source"
        position={isContainer ? Position.Right : Position.Bottom}
        className="custom-handle"
      />
    </div>
  );
};

export default memo(CustomNode);
