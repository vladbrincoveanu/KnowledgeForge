import { useState, type CSSProperties } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  EdgeProps,
  getSmoothStepPath,
} from "reactflow";

import { getC4EdgeGeometry } from "./c4EdgeGeometry";

const EDGE_COLORS: Record<string, string> = {
  uses: "#6366f1",
  calls: "#10b981",
  async: "#f59e0b",
  contains: "#8b5cf6",
  depends: "#ec4899",
  triggers: "#14b8a6",
};

const getEdgeColor = (data?: Record<string, unknown>): string => {
  if (!data?.relationship_type) return "#64748b";
  const relType = String(data.relationship_type).toLowerCase();
  return EDGE_COLORS[relType] || "#64748b";
};

const C4Edge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  label,
  data,
  interactionWidth,
  selected,
}: EdgeProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const edgeColor = getEdgeColor(data as Record<string, unknown>);
  const labelPlacement =
    data?.label_placement === "source" ||
    data?.label_placement === "target" ||
    data?.label_placement === "center"
      ? data.label_placement
      : undefined;
  const geometry = getC4EdgeGeometry({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    labelPlacement,
  });

  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY: sourceY + geometry.sourceYOffset,
    targetX,
    targetY: targetY + geometry.targetYOffset,
    sourcePosition,
    targetPosition,
    borderRadius: 0,
  });

  const protocol = data?.protocol as string | undefined;
  const description =
    typeof data?.description === "string" ? data.description.trim() : undefined;
  const fallbackLabel = typeof label === "string" ? label.trim() : undefined;
  const labelTitle =
    typeof data?.label_title === "string" ? data.label_title.trim() : undefined;
  const contextRole =
    typeof data?.context_role === "string" ? data.context_role : undefined;
  const primaryLabel = fallbackLabel || description || protocol;
  const secondaryDescription =
    protocol && protocol !== primaryLabel ? protocol : undefined;

  const hasContent = primaryLabel || secondaryDescription;
  const edgeLabelStyle = {
    "--edge-accent": edgeColor,
  } as CSSProperties;

  const showLabel = hasContent && (isHovered || selected);

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth ?? 20}
        style={{
          stroke: "rgba(248, 250, 252, 0.96)",
          strokeWidth: 8,
          strokeLinecap: "round",
          strokeLinejoin: "round",
        }}
        className="c4-edge-halo"
      />
      <BaseEdge
        id={`${id}-foreground`}
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth ?? 20}
        style={{
          stroke: edgeColor,
          strokeOpacity: 0.78,
          strokeWidth: 2.4,
          strokeLinecap: "round",
          strokeLinejoin: "round",
          cursor: "pointer",
          transition:
            "stroke 0.2s ease, stroke-width 0.2s ease, stroke-opacity 0.2s ease",
        }}
        className="c4-edge-line"
      />
      {showLabel ? (
        <EdgeLabelRenderer>
          <div
            className={`c4-edge-label${
              contextRole ? ` c4-edge-label--${contextRole}` : ""
            }`}
            style={{
              transform: `translate(-50%, -50%) translate(${geometry.labelX}px,${geometry.labelY}px)`,
            }}
          >
            <div className="c4-edge-label-inner" style={edgeLabelStyle}>
              <span className="c4-edge-label-accent" aria-hidden="true" />
              <div className="c4-edge-label-copy">
                {labelTitle && labelTitle !== primaryLabel ? (
                  <span className="c4-edge-title-chip">{labelTitle}</span>
                ) : null}
                {primaryLabel ? (
                  <span className="c4-edge-primary">{primaryLabel}</span>
                ) : null}
                {secondaryDescription && (
                  <span className="c4-edge-desc">{secondaryDescription}</span>
                )}
              </div>
            </div>
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};

export default C4Edge;
