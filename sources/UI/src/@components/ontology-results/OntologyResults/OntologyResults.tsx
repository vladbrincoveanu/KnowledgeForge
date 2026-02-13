import React, { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '@/services/api';

interface Entity {
  id?: string;
  name: string;
  entity_type: string;
  confidence: number;
  source_file?: string;
  column_name?: string;
  source_columns?: string[];
  attributes?: Record<string, unknown>;
}

interface Relationship {
  id?: string;
  source_entity_id?: string;
  target_entity_id?: string;
  relationship_type: string;
  confidence: number;
  source_file?: string;
}

interface Props {
  taskId: string;
  onFeedbackSubmitted: (feedback: unknown) => void;
  showNotification?: (message: string, type: 'success' | 'error' | 'info') => void;
}

interface ActiveFeedback {
  type: 'positive' | 'negative';
  entityId?: string;
  relationshipId?: string;
  comment: string;
}

const OntologyResults: React.FC<Props> = ({ taskId, onFeedbackSubmitted }) => {
  const [activeTab, setActiveTab] = useState<'entities' | 'relationships'>('entities');
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeFeedback, setActiveFeedback] = useState<ActiveFeedback | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setError(null);
      try {
        const [entitiesData, relationshipsData] = await Promise.all([
          ontologyAPI.getEntities(taskId),
          ontologyAPI.getRelationships(taskId),
        ]);
        if (!cancelled) {
          setEntities(entitiesData.items || []);
          setRelationships(relationshipsData.items || []);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load data');
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [taskId, refreshTrigger]);

  const handleExport = () => {
    const data = JSON.stringify({ entities, relationships }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ontology-results-${taskId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleFeedbackSubmit = async () => {
    if (!activeFeedback) return;
    await ontologyAPI.submitFeedback({
      type: activeFeedback.type,
      entity_id: activeFeedback.entityId,
      relationship_id: activeFeedback.relationshipId,
      comment: activeFeedback.comment,
    });
    onFeedbackSubmitted(activeFeedback);
    setActiveFeedback(null);
  };

  return (
    <div className="ontology-results">
      <div className="results-header">
        <h2>Extraction Results</h2>
        <div className="results-actions">
          <button onClick={() => setRefreshTrigger(t => t + 1)}>Refresh</button>
          <button onClick={handleExport}>Export Results</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="tabs">
        <button
          className={activeTab === 'entities' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('entities')}
        >
          Entities ({entities.length})
        </button>
        <button
          className={activeTab === 'relationships' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('relationships')}
        >
          Relationships ({relationships.length})
        </button>
      </div>

      {activeTab === 'entities' && (
        <div className="entities-content">
          {entities.map(entity => (
            <div key={entity.id || entity.name} className="entity-item">
              <span className="entity-name">{entity.name}</span>
              <span className="entity-type">{entity.entity_type}</span>
              <span
                className="entity-confidence"
                style={{ color: apiUtils.getConfidenceColor(entity.confidence) }}
              >
                {apiUtils.formatConfidence(entity.confidence)}
              </span>
              <button
                className="feedback-btn positive"
                onClick={() =>
                  setActiveFeedback({
                    type: 'positive',
                    entityId: entity.id,
                    relationshipId: undefined,
                    comment: '',
                  })
                }
              >
                +
              </button>
              <button
                className="feedback-btn negative"
                onClick={() =>
                  setActiveFeedback({
                    type: 'negative',
                    entityId: entity.id,
                    relationshipId: undefined,
                    comment: '',
                  })
                }
              >
                -
              </button>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'relationships' && (
        <div className="relationships-content">
          <h3>Discovered Relationships</h3>
          <p>{relationships.length} relationships found</p>
          {relationships.map(rel => (
            <div key={rel.id || rel.relationship_type} className="relationship-item">
              <span className="relationship-type">{rel.relationship_type}</span>
              <span
                className="relationship-confidence"
                style={{ color: apiUtils.getConfidenceColor(rel.confidence) }}
              >
                {apiUtils.formatConfidence(rel.confidence)}
              </span>
              <button
                className="feedback-btn positive"
                onClick={() =>
                  setActiveFeedback({
                    type: 'positive',
                    entityId: undefined,
                    relationshipId: rel.id,
                    comment: '',
                  })
                }
              >
                +
              </button>
              <button
                className="feedback-btn negative"
                onClick={() =>
                  setActiveFeedback({
                    type: 'negative',
                    entityId: undefined,
                    relationshipId: rel.id,
                    comment: '',
                  })
                }
              >
                -
              </button>
            </div>
          ))}
        </div>
      )}

      {activeFeedback && (
        <div className="feedback-form">
          <textarea
            value={activeFeedback.comment}
            onChange={e =>
              setActiveFeedback({ ...activeFeedback, comment: e.target.value })
            }
            placeholder="Add a comment (optional)"
          />
          <button onClick={handleFeedbackSubmit}>Submit Feedback</button>
          <button onClick={() => setActiveFeedback(null)}>Cancel</button>
        </div>
      )}
    </div>
  );
};

export default OntologyResults;
