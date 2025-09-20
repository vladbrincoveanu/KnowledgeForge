import React, { useMemo } from 'react';
import {
  EdgeSelectionState,
  EnhancedEdgeRecommendation,
} from './EdgeRecommendationList';

interface EdgeRecommendationCardProps {
  recommendation: EnhancedEdgeRecommendation;
  selection: EdgeSelectionState | undefined;
  onToggle: (edgeId: string) => void;
  onUpdateSelection: (edgeId: string, update: Partial<EdgeSelectionState>) => void;
}

const EdgeRecommendationCard: React.FC<EdgeRecommendationCardProps> = ({
  recommendation,
  selection,
  onToggle,
  onUpdateSelection,
}) => {
  const fallbackSelection = useMemo<EdgeSelectionState>(
    () => ({
      approved: true,
      relationshipType: recommendation.relationshipType,
      confidence: recommendation.confidence ?? 0.7,
      metadata: recommendation.metadata || {},
      reasoning: recommendation.reasoning,
    }),
    [recommendation]
  );

  const activeSelection = selection ?? fallbackSelection;
  const isSelected = activeSelection.approved;

  const handleToggle = () => {
    onToggle(recommendation.id);
  };

  const handleRelationshipTypeChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    onUpdateSelection(recommendation.id, {
      relationshipType: event.target.value,
    });
  };

  const handleConfidenceChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = Number(event.target.value) / 100;
    onUpdateSelection(recommendation.id, { confidence: value });
  };

  const handleReasoningChange = (
    event: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    onUpdateSelection(recommendation.id, { reasoning: event.target.value });
  };

  const connectionEvidence =
    recommendation.metadata?.evidence || recommendation.metadata || {};

  return (
    <div className={`edge-recommendation-card ${isSelected ? 'selected' : ''}`}>
      <div className="card-header">
        <div className="header-primary">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={handleToggle}
            className="selection-checkbox"
          />
          <div className="header-titles">
            <h4>
              {recommendation.sourceNodeId} → {recommendation.targetNodeId}
            </h4>
            <span className="connection-label">
              Suggested relationship: {recommendation.relationshipType}
            </span>
          </div>
        </div>
        <div className="confidence-indicator">
          <span className="confidence-value">
            {Math.round((activeSelection.confidence || 0) * 100)}%
          </span>
          <label>confidence</label>
        </div>
      </div>

      <div className="edge-config">
        <div className="form-field">
          <label htmlFor={`edge-type-${recommendation.id}`}>
            Relationship label
          </label>
          <input
            id={`edge-type-${recommendation.id}`}
            type="text"
            value={activeSelection.relationshipType}
            onChange={handleRelationshipTypeChange}
          />
        </div>

        <div className="form-field confidence-field">
          <label htmlFor={`edge-confidence-${recommendation.id}`}>
            Confidence calibration
          </label>
          <input
            id={`edge-confidence-${recommendation.id}`}
            type="range"
            min={40}
            max={100}
            step={1}
            value={Math.round((activeSelection.confidence || 0) * 100)}
            onChange={handleConfidenceChange}
          />
        </div>
      </div>

      <div className="metadata-section">
        <div className="metadata-block">
          <h5>Evidence</h5>
          <ul className="evidence-list">
            {Object.entries(connectionEvidence).map(([key, value]) => (
              <li key={key}>
                <strong>{key.replace(/_/g, ' ')}:</strong>{' '}
                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
              </li>
            ))}
            {Object.keys(connectionEvidence).length === 0 && (
              <li>No additional evidence provided.</li>
            )}
          </ul>
        </div>
      </div>

      <div className="reasoning-section">
        <h5>LLM rationale</h5>
        <textarea
          value={activeSelection.reasoning ?? recommendation.reasoning}
          onChange={handleReasoningChange}
          rows={3}
        />
      </div>
    </div>
  );
};

export default EdgeRecommendationCard;
