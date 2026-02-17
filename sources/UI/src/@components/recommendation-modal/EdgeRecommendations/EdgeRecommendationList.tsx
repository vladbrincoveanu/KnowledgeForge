import React from 'react';
import './EdgeRecommendationList.scss';

export interface EdgeRecommendation {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  relationshipType: string;
  confidence: number;
  reasoning?: string;
  metadata?: Record<string, any>;
}

export interface EnhancedEdgeRecommendation extends EdgeRecommendation {
  // Additional fields from API
}

export interface EdgeSelectionState {
  approved: boolean;
  relationshipType: string;
  confidence: number;
  metadata: Record<string, any>;
  reasoning?: string;
}

interface EdgeRecommendationListProps {
  recommendations: EnhancedEdgeRecommendation[];
  selections: Record<string, EdgeSelectionState>;
  onEdgeToggle: (edgeId: string) => void;
  onUpdateSelection: (edgeId: string, update: Partial<EdgeSelectionState>) => void;
  nodeLookup: Record<string, any>;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

const EdgeRecommendationList: React.FC<EdgeRecommendationListProps> = ({
  recommendations,
  selections,
  onEdgeToggle,
  nodeLookup,
  onSelectAll,
  onDeselectAll,
}) => {
  return (
    <div className="edge-recommendation-list">
      <div className="edge-list-header">
        <h3>Edge Recommendations ({recommendations.length})</h3>
        <div className="bulk-actions">
          <button onClick={onSelectAll} className="btn-select-all">
            Select All
          </button>
          <button onClick={onDeselectAll} className="btn-deselect-all">
            Deselect All
          </button>
        </div>
      </div>
      
      {recommendations.length === 0 ? (
        <p>No edge recommendations available.</p>
      ) : (
        <ul className="edge-list">
          {recommendations.map((edge) => {
            const selection = selections[edge.id];
            const sourceName = nodeLookup[edge.sourceNodeId]?.finalName || edge.sourceNodeId;
            const targetName = nodeLookup[edge.targetNodeId]?.finalName || edge.targetNodeId;
            
            return (
              <li key={edge.id} className={selection?.approved ? 'approved' : 'pending'}>
                <div className="edge-header">
                  <input
                    type="checkbox"
                    checked={selection?.approved ?? false}
                    onChange={() => onEdgeToggle(edge.id)}
                  />
                  <div className="edge-connection">
                    <span className="source-node">{sourceName}</span>
                    <span className="relationship-type">{edge.relationshipType}</span>
                    <span className="target-node">{targetName}</span>
                  </div>
                  <span className="confidence">
                    {(edge.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {edge.reasoning && (
                  <div className="edge-reasoning">{edge.reasoning}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default EdgeRecommendationList;
