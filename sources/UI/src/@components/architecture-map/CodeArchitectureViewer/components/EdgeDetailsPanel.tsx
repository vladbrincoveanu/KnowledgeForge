import React from 'react';

interface EdgeDetailsPanelProps {
  selectedEdge: any;
  onClose: () => void;
  edgeDescription: string;
  isEdgeLoading: boolean;
  variant?: "side" | "bottom" | "overlay";
  showClose?: boolean;
}

export default function EdgeDetailsPanel({
  selectedEdge,
  onClose,
  edgeDescription,
  isEdgeLoading,
  variant = "side",
  showClose = true,
}: EdgeDetailsPanelProps) {
  const label = selectedEdge?.data?.relationship_type || selectedEdge?.label || "Relationship";
  const protocol = selectedEdge?.data?.protocol || selectedEdge?.label;
  const from = selectedEdge?.data?.source_label || selectedEdge?.source || "";
  const to = selectedEdge?.data?.target_label || selectedEdge?.target || "";
  const desc = edgeDescription || selectedEdge?.data?.description || selectedEdge?.data?.llm_description || "";

  const isOverlay = variant === "overlay";
  const panelClass = `node-details-panel${isOverlay ? " ndp-overlay" : variant === "bottom" ? " bottom" : ""}`;

  return (
    <aside className={panelClass}>
      <div className="ndp-header">
        <div className="ndp-header-left">
          <span className="ndp-type-badge ndp-type-edge">relationship</span>
          <span className="ndp-name">{label}</span>
        </div>
        {showClose && <button className="ndp-close" onClick={onClose}>✕</button>}
      </div>

      <div className="ndp-body">
        {/* Flow diagram */}
        <div className="ndp-edge-flow">
          <span className="ndp-edge-node ndp-edge-source">{from}</span>
          <span className="ndp-edge-arrow">
            {protocol && <span className="ndp-edge-protocol">{protocol}</span>}
            →
          </span>
          <span className="ndp-edge-node ndp-edge-target">{to}</span>
        </div>

        {/* Description */}
        {(desc || isEdgeLoading) && (
          <p className="ndp-desc">{isEdgeLoading ? "Generating description…" : desc}</p>
        )}
      </div>
    </aside>
  );
}
