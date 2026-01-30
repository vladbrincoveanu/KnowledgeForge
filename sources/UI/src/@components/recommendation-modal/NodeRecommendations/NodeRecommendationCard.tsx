import React, { useState, useEffect } from 'react';
import {
  Check,
  X,
  Edit3,
  Save,
  RefreshCw,
  Key,
  BarChart3,
  Hash,
  Calendar,
  Type,
  HelpCircle,
} from 'lucide-react';
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
  decision?: 'approved' | 'rejected' | 'pending';
}

interface NodeRecommendationCardProps {
  recommendation: NodeRecommendation;
  selection: NodeSelectionState;
  onToggle: (nodeId: string) => void;
  onUpdateSelection: (
    nodeId: string,
    update: Partial<NodeSelectionState>
  ) => void;
  isEditing?: boolean;
  onEditToggle?: (nodeId: string, editing: boolean) => void;
}

const NodeRecommendationCard: React.FC<NodeRecommendationCardProps> = ({
  recommendation,
  selection,
  onToggle,
  onUpdateSelection,
  isEditing: _isEditing = false,
  onEditToggle,
}) => {
  const [editMode, setEditMode] = useState(false);
  const [tempName, setTempName] = useState(selection.finalName);
  const [tempEntityType, setTempEntityType] = useState(selection.entityType);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    setTempName(selection.finalName);
    setTempEntityType(selection.entityType);
  }, [selection.finalName, selection.entityType]);

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return '#10b981';
    if (confidence >= 0.6) return '#f59e0b';
    return '#ef4444';
  };

  const getEntityTypeIcon = (entityType: string) => {
    switch (entityType.toLowerCase()) {
      case 'identifier':
        return <Key size={12} />;
      case 'categorical':
        return <BarChart3 size={12} />;
      case 'numerical':
        return <Hash size={12} />;
      case 'datetime':
        return <Calendar size={12} />;
      case 'text':
        return <Type size={12} />;
      default:
        return <HelpCircle size={12} />;
    }
  };

  const handleStartEdit = () => {
    setEditMode(true);
    onEditToggle?.(recommendation.id, true);
  };

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

  return (
    <div
      className={`node-recommendation-card ${selection.approved ? 'approved' : 'declined'} ${editMode ? 'editing' : ''}`}
    >
      {/* Approval Toggle */}
      <div className="approval-toggle">
        <button
          className={`toggle-btn approve ${selection.approved ? 'active' : ''}`}
          onClick={() => onToggle(recommendation.id)}
          title="Approve this recommendation"
        >
          <Check size={12} />
        </button>
        <button
          className={`toggle-btn reject ${!selection.approved ? 'active' : ''}`}
          onClick={() => onToggle(recommendation.id)}
          title="Reject this recommendation"
        >
          <X size={12} />
        </button>
      </div>

      {/* Entity Icon */}
      <div className="entity-icon">
        {getEntityTypeIcon(selection.entityType)}
      </div>

      {/* Entity Info */}
      <div className="entity-info">
        <div className="entity-name">
          {editMode ? (
            <input
              type="text"
              value={tempName}
              onChange={e => setTempName(e.target.value)}
              className="entity-name-text"
              placeholder="Enter entity name..."
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') handleSaveEdit();
                if (e.key === 'Escape') handleCancelEdit();
              }}
            />
          ) : (
            <span className="entity-name-text">{selection.finalName}</span>
          )}

          <div className="entity-type-badge">
            {editMode ? (
              <select
                value={tempEntityType}
                onChange={e => setTempEntityType(e.target.value)}
                className="entity-type-select"
              >
                <option value="categorical">Categorical</option>
                <option value="numerical">Numerical</option>
                <option value="identifier">Identifier</option>
                <option value="datetime">DateTime</option>
                <option value="text">Text</option>
                <option value="unknown">Unknown</option>
              </select>
            ) : (
              <>
                <span className="entity-icon">
                  {getEntityTypeIcon(selection.entityType)}
                </span>
                <span className="entity-type-text">{selection.entityType}</span>
              </>
            )}
          </div>
        </div>

        <div className="entity-description">{recommendation.reasoning}</div>

        {recommendation.sourceColumns &&
          recommendation.sourceColumns.length > 0 && (
            <div className="source-columns">
              <strong>SOURCE COLUMNS:</strong>
              <div className="column-chips">
                {recommendation.sourceColumns.map((column, index) => (
                  <span key={index} className="column-chip">
                    {column}
                  </span>
                ))}
              </div>
            </div>
          )}
      </div>

      {/* Confidence Indicator */}
      <div className="confidence-indicator">
        <div
          className="confidence-bar"
          style={{
            backgroundColor: getConfidenceColor(selection.confidence),
          }}
        >
          {Math.round(selection.confidence * 100)}%
        </div>
      </div>

      {/* Card Actions */}
      <div className="card-actions">
        <button
          className="action-btn"
          onClick={editMode ? handleSaveEdit : handleStartEdit}
          title={editMode ? 'Save changes' : 'Edit name and type'}
        >
          {editMode ? <Save size={14} /> : <Edit3 size={14} />}
        </button>

        {editMode && (
          <button
            className="action-btn"
            onClick={handleCancelEdit}
            title="Cancel editing"
          >
            <X size={14} />
          </button>
        )}

        <button
          className="action-btn"
          onClick={() => setShowAdvanced(!showAdvanced)}
          title={
            showAdvanced ? 'Hide advanced details' : 'Show advanced details'
          }
        >
          <RefreshCw size={14} className={showAdvanced ? 'rotated' : ''} />
        </button>
      </div>

      {/* Advanced Details (when expanded) */}
      {showAdvanced && (
        <div className="advanced-details">
          <div className="metadata-section">
            <h4>Recommendation Metadata:</h4>
            <pre className="metadata-content">
              {JSON.stringify(
                recommendation.metadata || recommendation.llmMetadata || {},
                null,
                2
              )}
            </pre>
          </div>

          <div className="selection-metadata">
            <h4>Current Selection:</h4>
            <div className="selection-info">
              <p>
                <strong>Confidence:</strong>{' '}
                {Math.round(selection.confidence * 100)}%
              </p>
              <p>
                <strong>Linked Entity ID:</strong>{' '}
                {selection.linkedEntityId || 'None'}
              </p>
              <p>
                <strong>Source Columns:</strong>{' '}
                {selection.sourceColumns.join(', ') || 'None'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NodeRecommendationCard;
