import React, { useState, useEffect } from 'react';
import { Check, X, Edit3, Save, RefreshCw } from 'lucide-react';
import './NodeRecommendationCard.scss';

export interface NodeRecommendation {
  id: string;
  name: string;
  entityType: string;
  confidence: number;
  reasoning: string;
  sourceColumns?: string[];
  metadata?: Record<string, any>;
  llmMetadata?: Record<string, any>;
  linkedEntityId?: string;
}

export interface NodeSelectionState {
  approved: boolean;
  finalName: string;
  entityType: string;
  confidence: number;
  sourceColumns: string[];
  metadata: Record<string, any>;
  linkedEntityId?: string;
}

interface NodeRecommendationCardProps {
  recommendation: NodeRecommendation;
  selection: NodeSelectionState;
  onToggle: (nodeId: string) => void;
  onUpdateSelection: (nodeId: string, update: Partial<NodeSelectionState>) => void;
  isEditing?: boolean;
  onEditToggle?: (nodeId: string, editing: boolean) => void;
}

const NodeRecommendationCard: React.FC<NodeRecommendationCardProps> = ({
  recommendation,
  selection,
  onToggle,
  onUpdateSelection,
  isEditing = false,
  onEditToggle
}) => {
  const [editMode, setEditMode] = useState(false);
  const [tempName, setTempName] = useState(selection.finalName);
  const [tempEntityType, setTempEntityType] = useState(selection.entityType);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    setTempName(selection.finalName);
    setTempEntityType(selection.entityType);
  }, [selection.finalName, selection.entityType]);

  const handleSaveEdit = () => {
    if (tempName.trim()) {
      onUpdateSelection(recommendation.id, {
        finalName: tempName.trim(),
        entityType: tempEntityType,
      });
      setEditMode(false);
      onEditToggle?.(recommendation.id, false);
    }
  };

  const handleCancelEdit = () => {
    setTempName(selection.finalName);
    setTempEntityType(selection.entityType);
    setEditMode(false);
    onEditToggle?.(recommendation.id, false);
  };

  const handleStartEdit = () => {
    setEditMode(true);
    onEditToggle?.(recommendation.id, true);
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return '#10b981'; // green
    if (confidence >= 0.6) return '#f59e0b'; // yellow
    return '#ef4444'; // red
  };

  const getEntityTypeIcon = (entityType: string) => {
    switch (entityType.toLowerCase()) {
      case 'categorical': return '📊';
      case 'numerical': return '🔢';
      case 'identifier': return '🔑';
      case 'datetime': return '📅';
      case 'text': return '📝';
      default: return '📦';
    }
  };

  return (
    <div className={`node-recommendation-card ${selection.approved ? 'approved' : 'declined'} ${editMode ? 'editing' : ''}`}>
      <div className="card-header">
        <div className="approval-toggle">
          <button
            className={`toggle-btn approve ${selection.approved ? 'active' : ''}`}
            onClick={() => onToggle(recommendation.id)}
            title="Approve this recommendation"
          >
            <Check size={16} />
          </button>
          <button
            className={`toggle-btn decline ${!selection.approved ? 'active' : ''}`}
            onClick={() => onToggle(recommendation.id)}
            title="Decline this recommendation"
          >
            <X size={16} />
          </button>
        </div>

        <div className="confidence-indicator">
          <div 
            className="confidence-bar"
            style={{ backgroundColor: getConfidenceColor(selection.confidence) }}
          >
            {Math.round(selection.confidence * 100)}%
          </div>
        </div>
      </div>

      <div className="card-content">
        <div className="entity-info">
          <div className="entity-type-badge">
            <span className="entity-icon">{getEntityTypeIcon(selection.entityType)}</span>
            {editMode ? (
              <select
                value={tempEntityType}
                onChange={(e) => setTempEntityType(e.target.value)}
                className="entity-type-edit"
              >
                <option value="categorical">Categorical</option>
                <option value="numerical">Numerical</option>
                <option value="identifier">Identifier</option>
                <option value="datetime">DateTime</option>
                <option value="text">Text</option>
                <option value="unknown">Unknown</option>
              </select>
            ) : (
              <span className="entity-type-text">{selection.entityType}</span>
            )}
          </div>

          <div className="entity-name">
            {editMode ? (
              <div className="name-edit-container">
                <input
                  type="text"
                  value={tempName}
                  onChange={(e) => setTempName(e.target.value)}
                  className="name-edit-input"
                  placeholder="Enter entity name..."
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveEdit();
                    if (e.key === 'Escape') handleCancelEdit();
                  }}
                />
                <div className="edit-actions">
                  <button
                    className="save-btn"
                    onClick={handleSaveEdit}
                    disabled={!tempName.trim()}
                    title="Save changes (Enter)"
                  >
                    <Save size={14} />
                  </button>
                  <button
                    className="cancel-btn"
                    onClick={handleCancelEdit}
                    title="Cancel editing (Esc)"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="name-display">
                <h3 className="entity-name-text">{selection.finalName}</h3>
                <button
                  className="edit-btn"
                  onClick={handleStartEdit}
                  title="Edit name and type"
                >
                  <Edit3 size={14} />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="recommendation-details">
          <div className="reasoning">
            <p>{recommendation.reasoning}</p>
          </div>

          {recommendation.sourceColumns && recommendation.sourceColumns.length > 0 && (
            <div className="source-columns">
              <strong>Source Columns:</strong>
              <div className="columns-tags">
                {recommendation.sourceColumns.map((column, index) => (
                  <span key={index} className="column-tag">
                    {column}
                  </span>
                ))}
              </div>
            </div>
          )}

          <button
            className={`advanced-toggle ${showAdvanced ? 'expanded' : ''}`}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced
            <RefreshCw size={12} className={showAdvanced ? 'rotated' : ''} />
          </button>

          {showAdvanced && (
            <div className="advanced-details">
              <div className="metadata-section">
                <h4>Recommendation Metadata:</h4>
                <pre className="metadata-content">
                  {JSON.stringify(recommendation.metadata || recommendation.llmMetadata || {}, null, 2)}
                </pre>
              </div>
              
              <div className="selection-metadata">
                <h4>Current Selection:</h4>
                <div className="selection-info">
                  <p><strong>Confidence:</strong> {Math.round(selection.confidence * 100)}%</p>
                  <p><strong>Linked Entity ID:</strong> {selection.linkedEntityId || 'None'}</p>
                  <p><strong>Source Columns:</strong> {selection.sourceColumns.join(', ') || 'None'}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodeRecommendationCard;