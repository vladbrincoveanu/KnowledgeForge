import React from "react";

type Props = { decisionMode: "LLM_ADJUDICATED" | "NEEDS_REVIEW" | string };

const COLOR: Record<string, string> = {
  LLM_ADJUDICATED: "#7C3AED",
  NEEDS_REVIEW: "#F59E0B",
};

export const EnrichmentBadge: React.FC<Props> = ({ decisionMode }) => {
  const color = COLOR[decisionMode];
  if (!color) return null;
  return (
    <span
      role="status"
      aria-label={`Decision mode: ${decisionMode}`}
      style={{
        display: "inline-block",
        padding: "2px 6px",
        borderRadius: 4,
        background: color,
        color: "white",
        fontSize: 10,
        marginLeft: 6,
      }}
    >
      {decisionMode === "NEEDS_REVIEW" ? "REVIEW" : "LLM"}
    </span>
  );
};
