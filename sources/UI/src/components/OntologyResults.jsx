import React, { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '../services/api';
import { Database, Link, Eye, MessageSquare, ThumbsUp, ThumbsDown, RefreshCw, Download } from 'lucide-react';
import './OntologyResults.css';

const OntologyResults = ({ taskId, onFeedbackSubmitted }) => {
  const [entities, setEntities] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('entities');
  const [pagination, setPagination] = useState({
    entities: { page: 1, limit: 20, total: 0 },
    relationships: { page: 1, limit: 20, total: 0 }
  });
  const [feedbackForm, setFeedbackForm] = useState({
    entity_id: '',
    relationship_id: '',
    feedback_type: 'validate_entity',
    feedback_value: 'correct',
    confidence_delta: 0.1,
    user_id: 'user_' + Math.random().toString(36).substr(2, 9)
  });

  useEffect(() => {
    if (taskId) {
      checkTaskStatus();
    }
  }, [taskId]);

  // Check task status and load results if completed
  const checkTaskStatus = async () => {
    if (!taskId) return;
    
    try {
      const status = await ontologyAPI.getExtractionStatus(taskId);
      setTaskStatus(status);
      
      if (status.status === 'completed') {
        // Task is completed, load results
        loadResults();
      } else if (status.status === 'failed') {
        setError(`Extraction failed: ${status.error || 'Unknown error'}`);
        setLoading(false);
      } else {
        // Task is still in progress, poll for status
        setLoading(false);
        pollTaskStatus();
      }
    } catch (error) {
      console.error('Failed to check task status:', error);
      setError('Failed to check task status');
      setLoading(false);
    }
  };

  // Poll task status until completed
  const pollTaskStatus = () => {
    const interval = setInterval(async () => {
      try {
        const status = await ontologyAPI.getExtractionStatus(taskId);
        setTaskStatus(status);
        
        if (status.status === 'completed') {
          clearInterval(interval);
          loadResults();
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setError(`Extraction failed: ${status.error || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to poll task status:', error);
        clearInterval(interval);
        setError('Failed to check task status');
      }
    }, 2000); // Poll every 2 seconds
    
    // Cleanup interval on unmount
    return () => clearInterval(interval);
  };

  const loadResults = async () => {
    if (!taskId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Load entities and relationships in parallel
      const [entitiesData, relationshipsData] = await Promise.all([
        ontologyAPI.getEntities(taskId, pagination.entities.limit, 0),
        ontologyAPI.getRelationships(taskId, pagination.relationships.limit, 0)
      ]);

      setEntities(entitiesData.entities || []);
      setRelationships(relationshipsData.relationships || []);
      
      setPagination(prev => ({
        entities: { ...prev.entities, total: entitiesData.total_count || 0 },
        relationships: { ...prev.relationships, total: relationshipsData.total_count || 0 }
      }));
      
    } catch (error) {
      console.error('Failed to load results:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async (type) => {
    const currentPagination = pagination[type];
    const newPage = currentPagination.page + 1;
    const offset = (newPage - 1) * currentPagination.limit;
    
    try {
      let data;
      if (type === 'entities') {
        data = await ontologyAPI.getEntities(taskId, currentPagination.limit, offset);
        setEntities(prev => [...prev, ...(data.entities || [])]);
      } else {
        data = await ontologyAPI.getRelationships(taskId, currentPagination.limit, offset);
        setRelationships(prev => [...prev, ...(data.relationships || [])]);
      }
      
      setPagination(prev => ({
        ...prev,
        [type]: { ...prev[type], page: newPage }
      }));
    } catch (error) {
      console.error(`Failed to load more ${type}:`, error);
    }
  };

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const feedbackData = {
        ...feedbackForm,
        entity_id: feedbackForm.entity_id || undefined,
        relationship_id: feedbackForm.relationship_id || undefined
      };
      
      const result = await ontologyAPI.submitFeedback(feedbackData);
      
      // Reset form
      setFeedbackForm({
        entity_id: '',
        relationship_id: '',
        feedback_type: 'validate_entity',
        feedback_value: 'correct',
        confidence_delta: 0.1,
        user_id: 'user_' + Math.random().toString(36).substr(2, 9)
      });
      
      // Notify parent component
      if (onFeedbackSubmitted) {
        onFeedbackSubmitted(result);
      }
      
      alert('Feedback submitted successfully!');
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      alert('Failed to submit feedback: ' + error.message);
    }
  };

  const exportResults = async (format = 'json') => {
    try {
      let data;
      let filename;
      
      if (activeTab === 'entities') {
        data = entities;
        filename = `entities_${taskId}.${format}`;
      } else {
        data = relationships;
        filename = `relationships_${taskId}.${format}`;
      }
      
      if (format === 'json') {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      } else if (format === 'csv') {
        // Convert to CSV
        const headers = Object.keys(data[0] || {});
        const csvContent = [
          headers.join(','),
          ...data.map(row => headers.map(header => JSON.stringify(row[header] || '')).join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to export results:', error);
      alert('Failed to export results: ' + error.message);
    }
  };

  if (loading) {
    return (
      <div className="ontology-results loading">
        <RefreshCw className="spinner" size={24} />
        <p>Loading ontology results...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ontology-results error">
        <p>Error loading results: {error}</p>
        <button onClick={checkTaskStatus} className="btn-retry">
          <RefreshCw size={16} /> Retry
        </button>
      </div>
    );
  }

  // Show task status while extraction is in progress
  if (taskStatus && taskStatus.status !== 'completed') {
    return (
      <div className="ontology-results processing">
        <RefreshCw className="spinner" size={24} />
        <h3>Extraction in Progress</h3>
        <p>Status: {taskStatus.status}</p>
        {taskStatus.message && <p>{taskStatus.message}</p>}
        {taskStatus.error && <p className="error">Error: {taskStatus.error}</p>}
        <button onClick={checkTaskStatus} className="btn-refresh">
          <RefreshCw size={16} /> Check Status
        </button>
      </div>
    );
  }

  if (!entities.length && !relationships.length) {
    return (
      <div className="ontology-results empty">
        <Database size={48} />
        <h3>No Results Yet</h3>
        <p>The ontology extraction is still in progress or no results were found.</p>
      </div>
    );
  }

  return (
    <div className="ontology-results">
      <div className="results-header">
        <h3>
          {activeTab === 'entities' ? <Database size={20} /> : <Link size={20} />}
          Ontology Extraction Results
        </h3>
        
        <div className="results-actions">
          <button onClick={() => exportResults('json')} className="btn-export">
            <Download size={16} /> Export JSON
          </button>
          <button onClick={() => exportResults('csv')} className="btn-export">
            <Download size={16} /> Export CSV
          </button>
        </div>
      </div>

      <div className="results-tabs">
        <button
          className={`tab ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => setActiveTab('entities')}
        >
          <Database size={16} /> Entities ({entities.length})
        </button>
        <button
          className={`tab ${activeTab === 'relationships' ? 'active' : ''}`}
          onClick={() => setActiveTab('relationships')}
        >
          <Link size={16} /> Relationships ({relationships.length})
        </button>
      </div>

      <div className="results-content">
        {activeTab === 'entities' && (
          <div className="entities-list">
            {entities.map((entity, index) => (
              <div key={entity.id || index} className="entity-item">
                <div className="entity-header">
                  <h4>{entity.name}</h4>
                  <div className="entity-confidence">
                    <span 
                      className="confidence-badge"
                      style={{ backgroundColor: apiUtils.getConfidenceColor(entity.confidence) }}
                    >
                      {apiUtils.formatConfidence(entity.confidence)}
                    </span>
                  </div>
                </div>
                
                <div className="entity-details">
                  <div className="detail-row">
                    <strong>Type:</strong> {entity.entity_type}
                  </div>
                  {entity.source_column && (
                    <div className="detail-row">
                      <strong>Source Column:</strong> {entity.source_column}
                    </div>
                  )}
                  {entity.attributes && Object.keys(entity.attributes).length > 0 && (
                    <div className="detail-row">
                      <strong>Attributes:</strong>
                      <div className="attributes-list">
                        {Object.entries(entity.attributes).map(([key, value]) => (
                          <span key={key} className="attribute">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="entity-actions">
                  <button 
                    className="btn-feedback"
                    onClick={() => setFeedbackForm(prev => ({ ...prev, entity_id: entity.id }))}
                  >
                    <MessageSquare size={16} /> Provide Feedback
                  </button>
                </div>
              </div>
            ))}
            
            {pagination.entities.page * pagination.entities.limit < pagination.entities.total && (
              <button 
                onClick={() => loadMore('entities')}
                className="btn-load-more"
              >
                Load More Entities
              </button>
            )}
          </div>
        )}

        {activeTab === 'relationships' && (
          <div className="relationships-list">
            {relationships.map((relationship, index) => (
              <div key={relationship.id || index} className="relationship-item">
                <div className="relationship-header">
                  <h4>{relationship.relationship_type}</h4>
                  <div className="relationship-confidence">
                    <span 
                      className="confidence-badge"
                      style={{ backgroundColor: apiUtils.getConfidenceColor(relationship.confidence) }}
                    >
                      {apiUtils.formatConfidence(relationship.confidence)}
                    </span>
                  </div>
                </div>
                
                <div className="relationship-details">
                  <div className="detail-row">
                    <strong>From:</strong> {relationship.source_entity_id}
                  </div>
                  <div className="detail-row">
                    <strong>To:</strong> {relationship.target_entity_id}
                  </div>
                  {relationship.source_columns && relationship.source_columns.length > 0 && (
                    <div className="detail-row">
                      <strong>Source Columns:</strong> {relationship.source_columns.join(', ')}
                    </div>
                  )}
                  {relationship.attributes && Object.keys(relationship.attributes).length > 0 && (
                    <div className="detail-row">
                      <strong>Attributes:</strong>
                      <div className="attributes-list">
                        {Object.entries(relationship.attributes).map(([key, value]) => (
                          <span key={key} className="attribute">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="relationship-actions">
                  <button 
                    className="btn-feedback"
                    onClick={() => setFeedbackForm(prev => ({ ...prev, relationship_id: relationship.id }))}
                  >
                    <MessageSquare size={16} /> Provide Feedback
                  </button>
                </div>
              </div>
            ))}
            
            {pagination.relationships.page * pagination.relationships.limit < pagination.relationships.total && (
              <button 
                onClick={() => loadMore('relationships')}
                className="btn-load-more"
              >
                Load More Relationships
              </button>
            )}
          </div>
        )}
      </div>

      {/* Feedback Form */}
      <div className="feedback-section">
        <h4><MessageSquare size={16} /> Provide Feedback</h4>
        <form onSubmit={handleFeedbackSubmit} className="feedback-form">
          <div className="form-row">
            <div className="form-group">
              <label>Feedback Type:</label>
              <select
                value={feedbackForm.feedback_type}
                onChange={(e) => setFeedbackForm(prev => ({ ...prev, feedback_type: e.target.value }))}
              >
                <option value="validate_entity">Validate Entity</option>
                <option value="validate_relationship">Validate Relationship</option>
                <option value="suggest_correction">Suggest Correction</option>
                <option value="mark_false_positive">Mark False Positive</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Feedback Value:</label>
              <select
                value={feedbackForm.feedback_value}
                onChange={(e) => setFeedbackForm(prev => ({ ...prev, feedback_value: e.target.value }))}
              >
                <option value="correct">Correct</option>
                <option value="incorrect">Incorrect</option>
                <option value="partially_correct">Partially Correct</option>
                <option value="needs_review">Needs Review</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Confidence Adjustment:</label>
              <input
                type="range"
                min="-1.0"
                max="1.0"
                step="0.1"
                value={feedbackForm.confidence_delta}
                onChange={(e) => setFeedbackForm(prev => ({ ...prev, confidence_delta: parseFloat(e.target.value) }))}
              />
              <span>{feedbackForm.confidence_delta > 0 ? '+' : ''}{feedbackForm.confidence_delta}</span>
            </div>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Entity ID (optional):</label>
              <input
                type="text"
                value={feedbackForm.entity_id}
                onChange={(e) => setFeedbackForm(prev => ({ ...prev, entity_id: e.target.value }))}
                placeholder="Leave empty if not applicable"
              />
            </div>
            
            <div className="form-group">
              <label>Relationship ID (optional):</label>
              <input
                type="text"
                value={feedbackForm.relationship_id}
                onChange={(e) => setFeedbackForm(prev => ({ ...prev, relationship_id: e.target.value }))}
                placeholder="Leave empty if not applicable"
              />
            </div>
          </div>
          
          <button type="submit" className="btn-submit-feedback">
            <MessageSquare size={16} /> Submit Feedback
          </button>
        </form>
      </div>
    </div>
  );
};

export default OntologyResults;
