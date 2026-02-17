import React from 'react';
import NodeRecommendationCard, {
  NodeRecommendation,
  NodeSelectionState,
} from './NodeRecommendationCard';
import './NodeRecommendationList.scss';

export type { NodeRecommendation, NodeSelectionState };

export interface EnhancedNodeRecommendation extends NodeRecommendation {
  // Additional fields that might come from the API
}

interface NodeRecommendationListProps {
  recommendations: EnhancedNodeRecommendation[];
  selections: Record<string, NodeSelectionState>;
  onToggle: (nodeId: string) => void;
  onUpdateSelection: (nodeId: string, update: Partial<NodeSelectionState>) => void;
  onEditToggle?: (nodeId: string, editing: boolean) => void;
}

const NodeRecommendationList: React.FC<NodeRecommendationListProps> = ({
  recommendations,
  selections,
  onToggle,
  onUpdateSelection,
  onEditToggle,
}) => {
  return (
    <div className="node-recommendation-list">
      <h3>Node Recommendations</h3>
      {recommendations.length === 0 ? (
        <p>No node recommendations available.</p>
      ) : (
        <div className="recommendations-grid">
          {recommendations.map((rec) => (
            <NodeRecommendationCard
              key={rec.id}
              recommendation={rec}
              selection={selections[rec.id]}
              onToggle={onToggle}
              onUpdateSelection={onUpdateSelection}
              onEditToggle={onEditToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default NodeRecommendationList;
