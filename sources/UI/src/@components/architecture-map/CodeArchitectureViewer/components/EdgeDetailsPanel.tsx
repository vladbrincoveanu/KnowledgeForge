import React from 'react';

interface EdgeDetailsPanelProps {
  selectedEdge: any;
  onClose: () => void;
  edgeDescription: string;
  isEdgeLoading: boolean;
}

export default function EdgeDetailsPanel({
  selectedEdge,
  onClose,
  edgeDescription,
  isEdgeLoading,
}: EdgeDetailsPanelProps) {
  return (
    <aside className="node-details-panel">
      <div className="panel-header">
        <h3>{selectedEdge.label || 'Relationship'}</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      <div className="panel-content">
        <div className="detail-row description-row">
          <span className="detail-value description-text">
            {isEdgeLoading
              ? 'Generating description…'
              : (edgeDescription ||
                  selectedEdge?.data?.description ||
                  'No description available')}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-label">from</span>
          <span className="detail-value">{selectedEdge.source}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">to</span>
          <span className="detail-value">{selectedEdge.target}</span>
        </div>
      </div>
    </aside>
  );
}
