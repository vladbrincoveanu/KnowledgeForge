import React, { useState, useEffect } from 'react';
import './ConnectionOverviewModal.css';

const ConnectionOverviewModal = ({ connections, onClose, onConfirmAll, onRejectAll, onConnectionAction }) => {
  const [selectedConnections, setSelectedConnections] = useState(new Set());
  const [expandedConnection, setExpandedConnection] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Initialize selected connections (auto-select high confidence ones)
  useEffect(() => {
    const highConfidenceIds = connections
      .filter(conn => conn.confidence_score >= 0.8 || conn.ai_score >= 0.8)
      .map(conn => conn.id);
    setSelectedConnections(new Set(highConfidenceIds));
  }, [connections]);

  const handleConnectionToggle = (connectionId) => {
    const newSelected = new Set(selectedConnections);
    if (newSelected.has(connectionId)) {
      newSelected.delete(connectionId);
    } else {
      newSelected.add(connectionId);
    }
    setSelectedConnections(newSelected);
  };

  const handleConnectionAction = async (connectionId, action) => {
    setIsProcessing(true);
    try {
      await onConnectionAction(connectionId, action);
      // Remove from selected if it was selected
      const newSelected = new Set(selectedConnections);
      newSelected.delete(connectionId);
      setSelectedConnections(newSelected);
    } catch (error) {
      console.error('Error handling connection action:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleConfirmAll = async () => {
    setIsProcessing(true);
    try {
      await onConfirmAll(Array.from(selectedConnections));
      setSelectedConnections(new Set());
    } catch (error) {
      console.error('Error confirming all connections:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRejectAll = async () => {
    setIsProcessing(true);
    try {
      await onRejectAll(Array.from(selectedConnections));
      setSelectedConnections(new Set());
    } catch (error) {
      console.error('Error rejecting all connections:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.9) return '#10b981';
    if (confidence >= 0.7) return '#f59e0b';
    return '#ef4444';
  };

  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.9) return 'High';
    if (confidence >= 0.7) return 'Medium';
    return 'Low';
  };

  const selectedCount = selectedConnections.size;
  const totalCount = connections.length;

  return (
    <div className="connection-overview-overlay" onClick={onClose}>
      <div className="connection-overview-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="overview-header">
          <div className="header-content">
            <h2>AI-Recommended Connections</h2>
            <div className="connection-stats">
              <span className="stat-item">
                <strong>{totalCount}</strong> connections found
              </span>
              <span className="stat-item">
                <strong>{selectedCount}</strong> selected
              </span>
            </div>
          </div>
          <button className="close-button" onClick={onClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="overview-content">
          <div className="connections-list">
            {connections.map((connection, index) => (
              <div key={connection.id} className="connection-item">
                <div className="connection-header">
                  <div className="connection-info">
                    <div className="connection-pair">
                      <span className="dataset-name">{connection.source_collection}</span>
                      <span className="column-pill">{connection.source_column}</span>
                      <span className="arrow">→</span>
                      <span className="dataset-name">{connection.target_collection}</span>
                      <span className="column-pill">{connection.target_column}</span>
                    </div>
                    <div className="connection-meta">
                      <span className="confidence-badge" style={{ backgroundColor: getConfidenceColor(connection.confidence_score || connection.ai_score) }}>
                        {Math.round((connection.confidence_score || connection.ai_score) * 100)}% CONFIDENCE
                      </span>
                      <span className="connection-type-badge">{connection.connection_type || 'FOREIGN_KEY'}</span>
                      <span className="join-strategy-badge">{connection.llm_analysis?.suggested_join_strategy || 'inner_join'}</span>
                    </div>
                  </div>
                  
                  <div className="connection-actions">
                    <label className="checkbox-container">
                      <input
                        type="checkbox"
                        checked={selectedConnections.has(connection.id)}
                        onChange={() => handleConnectionToggle(connection.id)}
                        disabled={isProcessing}
                      />
                      <span className="checkmark"></span>
                    </label>
                    
                    <button
                      className="action-button approve"
                      onClick={() => handleConnectionAction(connection.id, 'approve')}
                      disabled={isProcessing}
                      title="Approve this connection"
                    >
                      ✓
                    </button>
                    
                    <button
                      className="action-button reject"
                      onClick={() => handleConnectionAction(connection.id, 'reject')}
                      disabled={isProcessing}
                      title="Reject this connection"
                    >
                      ✕
                    </button>
                    
                    <button
                      className="action-button expand"
                      onClick={() => setExpandedConnection(expandedConnection === connection.id ? null : connection.id)}
                      title="View details"
                    >
                      {expandedConnection === connection.id ? '−' : '+'}
                    </button>
                  </div>
                </div>

                {/* Expanded details */}
                {expandedConnection === connection.id && (
                  <div className="connection-details">
                    <div className="ai-analysis">
                      <h4>AI Analysis</h4>
                      
                      {connection.llm_analysis ? (
                        <>
                          <div className="analysis-grid">
                            <div className="analysis-item">
                              <strong>Reasoning:</strong>
                              <p>{connection.llm_analysis.reasoning || 'AI analysis not available'}</p>
                            </div>
                            <div className="analysis-item">
                              <strong>Business Context:</strong>
                              <p>{connection.llm_analysis.business_context || 'Context not available'}</p>
                            </div>
                            <div className="analysis-item">
                              <strong>Connection Type:</strong>
                              <div className="type-badge">{connection.llm_analysis.connection_type || connection.connection_type || 'FOREIGN_KEY'}</div>
                            </div>
                            <div className="analysis-item">
                              <strong>Join Strategy:</strong>
                              <div className="strategy-badge">{connection.llm_analysis.suggested_join_strategy || 'inner_join'}</div>
                            </div>
                          </div>
                          
                          {connection.llm_analysis.potential_issues?.length > 0 && (
                            <div className="issues-section">
                              <h5>⚠️ Potential Issues</h5>
                              <ul>
                                {connection.llm_analysis.potential_issues.map((issue, idx) => (
                                  <li key={idx}>{issue}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          {connection.llm_analysis.recommendations?.length > 0 && (
                            <div className="recommendations-section">
                              <h5>💡 Recommendations</h5>
                              <ul>
                                {connection.llm_analysis.recommendations.map((rec, idx) => (
                                  <li key={idx}>{rec}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="fallback-analysis">
                          <p>AI analysis not available for this connection.</p>
                          <div className="connection-summary">
                            <strong>Connection Summary:</strong>
                            <p>This connection links {connection.source_column} from {connection.source_collection} to {connection.target_column} from {connection.target_collection}.</p>
                            <p>Confidence: {Math.round((connection.confidence_score || connection.ai_score) * 100)}%</p>
                            <p>Type: {connection.connection_type || 'FOREIGN_KEY'}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="overview-footer">
          <div className="footer-actions">
            <button
              className="secondary-button"
              onClick={onClose}
              disabled={isProcessing}
            >
              Cancel
            </button>
            
            <div className="bulk-actions">
              <button
                className="reject-all-button"
                onClick={handleRejectAll}
                disabled={selectedCount === 0 || isProcessing}
              >
                Reject Selected ({selectedCount})
              </button>
              
              <button
                className="confirm-all-button"
                onClick={handleConfirmAll}
                disabled={selectedCount === 0 || isProcessing}
              >
                Confirm Selected ({selectedCount})
              </button>
            </div>
          </div>
          
          <div className="footer-help">
            <small>
              💡 <strong>Tip:</strong> Select connections using checkboxes for bulk actions, or use individual approve/reject buttons. 
              High-confidence connections are auto-selected.
            </small>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConnectionOverviewModal; 