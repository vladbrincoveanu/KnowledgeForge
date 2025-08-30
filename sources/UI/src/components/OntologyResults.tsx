import React, { useCallback } from 'react';
import { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '../services/api';
import {
  Database,
  Download,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  FileText,
  AlertCircle,
} from 'lucide-react';
import {
  Entity,
  Relationship,
  PaginationState,
  FeedbackForm,
  PaginatedResponse,
  FeedbackResponse,
} from '../types';
import './OntologyResults.css';

interface OntologyResultsProps {
  taskId: string;
  onFeedbackSubmitted: (feedback: FeedbackResponse) => void;
}

const OntologyResults: React.FC<OntologyResultsProps> = ({
  taskId,
  onFeedbackSubmitted,
}) => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'entities' | 'relationships'>(
    'entities'
  );
  const [pagination, setPagination] = useState<PaginationState>({
    entities: { page: 1, limit: 20, total: 0 },
    relationships: { page: 1, limit: 20, total: 0 },
  });
  const [feedbackForm, setFeedbackForm] = useState<FeedbackForm>({
    entity_id: undefined,
    relationship_id: undefined,
    feedback_type: 'positive',
    feedback_value: '',
    confidence_delta: 0,
    user_id: 'current_user',
  });

  const loadData = useCallback(
    async (type: 'entities' | 'relationships', reset = false) => {
      try {
        setLoading(true);
        setError(null);

        const currentPagination = pagination[type];
        const page = reset ? 1 : currentPagination.page;

        let data: PaginatedResponse<Entity> | PaginatedResponse<Relationship>;
        if (type === 'entities') {
          data = await ontologyAPI.getEntities(
            taskId,
            currentPagination.limit,
            (page - 1) * currentPagination.limit
          );
          if (reset) {
            setEntities(data.items || []);
          } else {
            setEntities(prev => [...prev, ...(data.items || [])]);
          }
        } else {
          data = await ontologyAPI.getRelationships(
            taskId,
            currentPagination.limit,
            (page - 1) * currentPagination.limit
          );
          if (reset) {
            setRelationships(data.items || []);
          } else {
            setRelationships(prev => [...prev, ...(data.items || [])]);
          }
        }

        const newPage = reset ? 2 : page + 1;
        setPagination(prev => ({
          ...prev,
          [type]: { ...prev[type], page: newPage, total: data.total || 0 },
        }));
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'An unknown error occurred';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [taskId, pagination]
  );

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const feedbackData = {
        type: feedbackForm.feedback_type as 'positive' | 'negative',
        entity_id: feedbackForm.entity_id,
        relationship_id: feedbackForm.relationship_id,
        comment: feedbackForm.feedback_value,
      };

      const result = await ontologyAPI.submitFeedback(feedbackData);

      // Reset form
      setFeedbackForm({
        entity_id: undefined,
        relationship_id: undefined,
        feedback_type: 'positive',
        feedback_value: '',
        confidence_delta: 0,
        user_id: 'current_user',
      });

      // Notify parent component
      onFeedbackSubmitted(result);

      // Refresh data
      loadData(activeTab, true);

      alert('Feedback submitted successfully!');
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to submit feedback: ' + errorMessage);
    }
  };

  const handleExport = async () => {
    try {
      const data = {
        entities,
        relationships,
        taskId,
        exportedAt: new Date().toISOString(),
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ontology-results-${taskId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to export results: ' + errorMessage);
    }
  };

  const loadMore = () => {
    loadData(activeTab);
  };

  useEffect(() => {
    if (taskId) {
      loadData('entities', true);
      loadData('relationships', true);
    }
  }, [taskId, loadData]);

  return (
    <div className="ontology-results">
      {/* Header */}
      <div className="results-header">
        <div className="header-info">
          <h2>Extraction Results</h2>
          <p>Task ID: {taskId}</p>
        </div>

        <div className="header-actions">
          <button onClick={handleExport} className="export-button">
            <Download size={16} />
            Export Results
          </button>

          <button
            onClick={() => loadData(activeTab, true)}
            className="refresh-button"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="results-tabs">
        <button
          className={`tab ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => setActiveTab('entities')}
        >
          <Database size={16} />
          Entities ({entities.length})
        </button>

        <button
          className={`tab ${activeTab === 'relationships' ? 'active' : ''}`}
          onClick={() => setActiveTab('relationships')}
        >
          <FileText size={16} />
          Relationships ({relationships.length})
        </button>
      </div>

      {/* Content */}
      <div className="results-content">
        {error && (
          <div className="error-message">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {activeTab === 'entities' && (
          <div className="entities-section">
            <div className="section-header">
              <h3>Extracted Entities</h3>
              <span className="count">{entities.length} entities found</span>
            </div>

            <div className="entities-list">
              {entities.map((entity, index) => (
                <div key={entity.id || index} className="entity-item">
                  <div className="entity-header">
                    <h4>{entity.name}</h4>
                    <div
                      className="confidence-badge"
                      style={{
                        backgroundColor: apiUtils.getConfidenceColor(
                          entity.confidence
                        ),
                      }}
                    >
                      {apiUtils.formatConfidence(entity.confidence)}
                    </div>
                  </div>

                  <div className="entity-details">
                    <div className="detail-item">
                      <strong>Type:</strong> {entity.entity_type}
                    </div>
                    {entity.source_column && (
                      <div className="detail-item">
                        <strong>Source Column:</strong> {entity.source_column}
                      </div>
                    )}
                    {entity.attributes &&
                      Object.keys(entity.attributes).length > 0 && (
                        <div className="detail-item">
                          <strong>Attributes:</strong>
                          <ul className="attributes-list">
                            {Object.entries(entity.attributes).map(
                              ([key, value]) => (
                                <li key={key}>
                                  <strong>{key}:</strong> {String(value)}
                                </li>
                              )
                            )}
                          </ul>
                        </div>
                      )}
                  </div>

                  <div className="entity-actions">
                    <button
                      className="feedback-button positive"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          entity_id: entity.id,
                        }))
                      }
                    >
                      <ThumbsUp size={16} />
                    </button>

                    <button
                      className="feedback-button negative"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          entity_id: entity.id,
                          feedback_type: 'negative',
                        }))
                      }
                    >
                      <ThumbsDown size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'relationships' && (
          <div className="relationships-section">
            <div className="section-header">
              <h3>Discovered Relationships</h3>
              <span className="count">
                {relationships.length} relationships found
              </span>
            </div>

            <div className="relationships-list">
              {relationships.map((relationship, index) => (
                <div
                  key={relationship.id || index}
                  className="relationship-item"
                >
                  <div className="relationship-header">
                    <h4>{relationship.relationship_type}</h4>
                    <div
                      className="confidence-badge"
                      style={{
                        backgroundColor: apiUtils.getConfidenceColor(
                          relationship.confidence
                        ),
                      }}
                    >
                      {apiUtils.formatConfidence(relationship.confidence)}
                    </div>
                  </div>

                  <div className="relationship-details">
                    <div className="detail-item">
                      <strong>From:</strong> {relationship.source_entity_id}
                    </div>
                    <div className="detail-item">
                      <strong>To:</strong> {relationship.target_entity_id}
                    </div>
                    {relationship.source_columns &&
                      relationship.source_columns.length > 0 && (
                        <div className="detail-item">
                          <strong>Source Columns:</strong>{' '}
                          {relationship.source_columns.join(', ')}
                        </div>
                      )}
                    {relationship.attributes &&
                      Object.keys(relationship.attributes).length > 0 && (
                        <div className="detail-item">
                          <strong>Attributes:</strong>
                          <ul className="attributes-list">
                            {Object.entries(relationship.attributes).map(
                              ([key, value]) => (
                                <li key={key}>
                                  <strong>{key}:</strong> {String(value)}
                                </li>
                              )
                            )}
                          </ul>
                        </div>
                      )}
                  </div>

                  <div className="relationship-actions">
                    <button
                      className="feedback-button positive"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          relationship_id: relationship.id,
                        }))
                      }
                    >
                      <ThumbsUp size={16} />
                    </button>

                    <button
                      className="feedback-button negative"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          relationship_id: relationship.id,
                          feedback_type: 'negative',
                        }))
                      }
                    >
                      <ThumbsDown size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Load More Button */}
        {((activeTab === 'entities' &&
          entities.length < pagination.entities.total) ||
          (activeTab === 'relationships' &&
            relationships.length < pagination.relationships.total)) && (
          <div className="load-more-section">
            <button
              onClick={loadMore}
              className="load-more-button"
              disabled={loading}
            >
              {loading ? (
                <RefreshCw className="spinning" size={16} />
              ) : (
                'Load More'
              )}
            </button>
          </div>
        )}
      </div>

      {/* Feedback Form */}
      {(feedbackForm.entity_id || feedbackForm.relationship_id) && (
        <div className="feedback-overlay">
          <div className="feedback-form">
            <h3>Provide Feedback</h3>
            <form onSubmit={handleFeedbackSubmit}>
              <div className="form-group">
                <label>Feedback Type:</label>
                <select
                  value={feedbackForm.feedback_type}
                  onChange={e =>
                    setFeedbackForm(prev => ({
                      ...prev,
                      feedback_type: e.target.value,
                    }))
                  }
                >
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                </select>
              </div>

              <div className="form-group">
                <label>Comments:</label>
                <textarea
                  value={feedbackForm.feedback_value}
                  onChange={e =>
                    setFeedbackForm(prev => ({
                      ...prev,
                      feedback_value: e.target.value,
                    }))
                  }
                  placeholder="Optional feedback comments..."
                />
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  onClick={() =>
                    setFeedbackForm({
                      entity_id: undefined,
                      relationship_id: undefined,
                      feedback_type: 'positive',
                      feedback_value: '',
                      confidence_delta: 0,
                      user_id: 'current_user',
                    })
                  }
                >
                  Cancel
                </button>
                <button type="submit">Submit Feedback</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default OntologyResults;
