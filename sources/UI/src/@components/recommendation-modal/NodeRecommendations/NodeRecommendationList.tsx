import React, { useState } from 'react';
import { Plus, Sparkles, Users, Check, X } from 'lucide-react';
import NodeRecommendationCard from './NodeRecommendationCard';
import './NodeRecommendationList.scss';

export interface EnhancedNodeRecommendation {
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

interface NodeRecommendationListProps {
  recommendations: EnhancedNodeRecommendation[];
  selections: Record<string, NodeSelectionState>;
  onNodeToggle: (nodeId: string) => void;
  onUpdateSelection: (nodeId: string, update: Partial<NodeSelectionState>) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

const NodeRecommendationList: React.FC<NodeRecommendationListProps> = ({
  recommendations,
  selections,
  onNodeToggle,
  onUpdateSelection,
  onSelectAll,
  onDeselectAll,
}) => {
  const [showAddCustom, setShowAddCustom] = useState(false);
  const [customNodeName, setCustomNodeName] = useState('');
  const [customNodeType, setCustomNodeType] = useState('categorical');
  const [editingNodes, setEditingNodes] = useState<Set<string>>(new Set());

  const handleAddCustomNode = () => {
    if (customNodeName.trim()) {
      const customNodeId = `custom_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      const customSelection: NodeSelectionState = {
        approved: true,
        finalName: customNodeName.trim(),
        entityType: customNodeType,
        confidence: 1.0,
        sourceColumns: [],
        metadata: { 
          custom: true,
          created_at: new Date().toISOString(),
          user_created: true
        },
      };

      // Add the custom selection
      onUpdateSelection(customNodeId, customSelection);
      
      // Reset form
      setCustomNodeName('');
      setCustomNodeType('categorical');
      setShowAddCustom(false);
    }
  };

  const handleEditToggle = (nodeId: string, editing: boolean) => {
    const newEditingNodes = new Set(editingNodes);
    if (editing) {
      newEditingNodes.add(nodeId);
    } else {
      newEditingNodes.delete(nodeId);
    }
    setEditingNodes(newEditingNodes);
  };

  const approvedCount = Object.values(selections).filter(sel => sel?.approved).length;
  const totalCount = recommendations.length;
  const customNodesCount = Object.entries(selections).filter(([id, sel]) => 
    sel?.metadata?.custom && sel?.approved
  ).length;

  const handleCancelCustom = () => {
    setShowAddCustom(false);
    setCustomNodeName('');
    setCustomNodeType('categorical');
  };

  return (
    <div className="node-recommendation-list">
      <div className="list-header">
        <div className="list-title">
          <Users size={20} />
          <h3>Node Recommendations</h3>
          <div className="recommendation-stats">
            <span className="stat-badge primary">{totalCount} Generated</span>
            <span className="stat-badge success">{approvedCount} Approved</span>
            {customNodesCount > 0 && (
              <span className="stat-badge custom">{customNodesCount} Custom</span>
            )}
          </div>
        </div>

        <div className="list-controls">
          <div className="bulk-actions">
            <button 
              onClick={onSelectAll} 
              className="control-btn success"
              title="Approve all recommendations"
              disabled={totalCount === 0}
            >
              <Check size={14} />
              All
            </button>
            <button 
              onClick={onDeselectAll} 
              className="control-btn danger"
              title="Decline all recommendations"
              disabled={totalCount === 0}
            >
              <X size={14} />
              None
            </button>
          </div>

          <button 
            className="add-custom-btn primary"
            onClick={() => setShowAddCustom(!showAddCustom)}
            title="Add custom node recommendation"
          >
            <Plus size={14} />
            Add Custom
          </button>
        </div>
      </div>

      {showAddCustom && (
        <div className="add-custom-node">
          <div className="add-custom-header">
            <div className="custom-icon">
              <Plus size={16} />
            </div>
            <div className="custom-title">
              <h4>Add Custom Node</h4>
              <p>Create a manual entity recommendation with your preferred naming</p>
            </div>
          </div>
          
          <div className="add-custom-form">
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="customNodeName">Node Name *</label>
                <input
                  id="customNodeName"
                  type="text"
                  value={customNodeName}
                  onChange={(e) => setCustomNodeName(e.target.value)}
                  placeholder="e.g., Customer ID, Product Name..."
                  className="custom-name-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddCustomNode();
                    if (e.key === 'Escape') handleCancelCustom();
                  }}
                  autoFocus
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="customNodeType">Entity Type</label>
                <select
                  id="customNodeType"
                  value={customNodeType}
                  onChange={(e) => setCustomNodeType(e.target.value)}
                  className="custom-type-select"
                >
                  <option value="categorical">📊 Categorical</option>
                  <option value="numerical">🔢 Numerical</option>
                  <option value="identifier">🔑 Identifier</option>
                  <option value="datetime">📅 DateTime</option>
                  <option value="text">📝 Text</option>
                  <option value="unknown">❓ Unknown</option>
                </select>
              </div>
            </div>
            
            <div className="form-actions">
              <button
                className="cancel-btn"
                onClick={handleCancelCustom}
              >
                Cancel
              </button>
              <button
                className="add-btn"
                onClick={handleAddCustomNode}
                disabled={!customNodeName.trim()}
              >
                <Plus size={14} />
                Add Custom Node
              </button>
            </div>
          </div>
        </div>
      )}

      {totalCount === 0 && !showAddCustom ? (
        <div className="empty-state">
          <div className="empty-state-content">
            <Sparkles size={48} className="empty-icon" />
            <h3>No Automatic Recommendations</h3>
            <p>
              The system didn't generate any automatic node recommendations for this dataset. 
              You can manually create custom nodes using the button above.
            </p>
            <button 
              className="empty-action-btn"
              onClick={() => setShowAddCustom(true)}
            >
              <Plus size={16} />
              Create First Custom Node
            </button>
          </div>
        </div>
      ) : (
        <div className="recommendations-container">
          {recommendations.map((recommendation) => {
            const selection = selections[recommendation.id];
            if (!selection) return null;

            return (
              <NodeRecommendationCard
                key={recommendation.id}
                recommendation={recommendation}
                selection={selection}
                onToggle={onNodeToggle}
                onUpdateSelection={onUpdateSelection}
                isEditing={editingNodes.has(recommendation.id)}
                onEditToggle={handleEditToggle}
              />
            );
          })}
          
          {/* Show custom nodes that aren't in recommendations */}
          {Object.entries(selections)
            .filter(([id, sel]) => sel?.metadata?.custom && !recommendations.find(r => r.id === id))
            .map(([customId, selection]) => {
              // Create a fake recommendation for custom nodes
              const customRecommendation: EnhancedNodeRecommendation = {
                id: customId,
                name: selection.finalName,
                entityType: selection.entityType,
                confidence: selection.confidence,
                reasoning: 'Custom node created by user',
                sourceColumns: selection.sourceColumns,
                metadata: { ...selection.metadata, custom: true }
              };

              return (
                <NodeRecommendationCard
                  key={customId}
                  recommendation={customRecommendation}
                  selection={selection}
                  onToggle={onNodeToggle}
                  onUpdateSelection={onUpdateSelection}
                  isEditing={editingNodes.has(customId)}
                  onEditToggle={handleEditToggle}
                />
              );
            })}
        </div>
      )}

      {(totalCount > 0 || Object.keys(selections).some(id => selections[id]?.metadata?.custom)) && (
        <div className="list-summary">
          <div className="summary-stats">
            <div className="summary-item">
              <span className="summary-label">Total Nodes:</span>
              <span className="summary-value">{totalCount + customNodesCount}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Approved:</span>
              <span className="summary-value approved">{approvedCount}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Custom Added:</span>
              <span className="summary-value custom">{customNodesCount}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NodeRecommendationList;