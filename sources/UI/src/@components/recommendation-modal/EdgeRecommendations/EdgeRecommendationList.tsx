import React from 'react';
import EdgeRecommendationCard from './EdgeRecommendationCard';

export interface EnhancedEdgeRecommendation {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  relationshipType: string;
  confidence: number;
  reasoning: string;
  metadata?: Record<string, any>;
}

export interface EdgeSelectionState {
  approved: boolean;
  relationshipType: string;
  confidence: number;
  metadata: Record<string, any>;
  reasoning?: string;
  decision?: 'approved' | 'rejected' | 'pending';
}

interface EdgeRecommendationListProps {
  recommendations: EnhancedEdgeRecommendation[];
  selections: Record<string, EdgeSelectionState>;
  onEdgeToggle: (edgeId: string) => void;
  onUpdateSelection: (
    edgeId: string,
    update: Partial<EdgeSelectionState>
  ) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

const EdgeRecommendationList: React.FC<EdgeRecommendationListProps> = ({
  recommendations,
  selections,
  onEdgeToggle,
  onUpdateSelection,
  onSelectAll,
  onDeselectAll,
}) => {
  const selectedCount = Object.values(selections).filter(
    sel => sel?.approved
  ).length;

  return (
    <div className="edge-recommendation-list">
      <div className="list-header">
        <h3>Recommended Edges ({recommendations.length})</h3>
        <div className="selection-controls">
          <button onClick={onSelectAll} className="select-button">
            Select All
          </button>
          <button onClick={onDeselectAll} className="select-button">
            Deselect All
          </button>
          <span className="selection-count">
            {selectedCount} of {recommendations.length} curated
          </span>
        </div>
      </div>
      {recommendations.map(rec => (
        <EdgeRecommendationCard
          key={rec.id}
          recommendation={rec}
          selection={selections[rec.id]}
          onToggle={onEdgeToggle}
          onUpdateSelection={onUpdateSelection}
        />
      ))}
      {recommendations.length === 0 && (
        <div className="empty-state">
          <p>No edge recommendations were generated for this dataset.</p>
        </div>
      )}
    </div>
  );
};

export default EdgeRecommendationList;
