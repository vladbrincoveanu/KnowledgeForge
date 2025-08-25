import React, { useEffect } from 'react';
import './ConnectionPrompt.css';

const ConnectionPrompt = ({ connection, onResponse, onClose }) => {
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const handleYes = () => {
    onResponse(true, connection);
  };

  const handleCancel = () => {
    onResponse(false, connection);
  };

  const handleClose = () => {
    onClose();
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.9) return '#10b981'; // Green
    if (confidence >= 0.7) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };

  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.9) return 'High';
    if (confidence >= 0.7) return 'Medium';
    return 'Low';
  };

  return (
    <div className="connection-prompt-overlay" onClick={handleClose}>
      <div className="connection-prompt" onClick={(e) => e.stopPropagation()}>
        {/* Header with X button */}
        <div className="prompt-header">
          <div className="header-content">
            <h2>AI-Detected Connection</h2>
            <div className="confidence-badge" style={{ backgroundColor: getConfidenceColor(connection.confidence) }}>
              {Math.round(connection.confidence * 100)}% CONFIDENCE
            </div>
          </div>
          <button className="close-button" onClick={handleClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
        
        <div className="prompt-content">
          {/* Visual Discovery Highlight */}
          <div className="discovery-highlight">
            <div className="highlight-icon">🎯</div>
            <div className="highlight-content">
              <h4>AI-Powered Visual Discovery</h4>
              <p>Our AI analyzed your data files and discovered this potential connection. Review the analysis below and validate with a single click.</p>
            </div>
          </div>

          {/* Dataset Overview */}
          <div className="dataset-overview">
            <div className="dataset-card">
              <div className="dataset-name">{connection.fileA}</div>
              <div className="column-pill">{connection.columnA}</div>
            </div>
            
            <div className="connection-arrow">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M7 17L17 7M17 7H7M17 7V17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            
            <div className="dataset-card">
              <div className="dataset-name">{connection.fileB}</div>
              <div className="column-pill">{connection.columnB}</div>
            </div>
          </div>

          {/* AI Analysis */}
          {connection.llmAnalysis && (
            <div className="ai-analysis-section">
              <h3>AI Analysis</h3>
              
              <div className="analysis-grid">
                <div className="analysis-card">
                  <h4>Reasoning</h4>
                  <p>{connection.llmAnalysis.reasoning}</p>
                </div>
                
                <div className="analysis-card">
                  <h4>Business Context</h4>
                  <p>{connection.llmAnalysis.business_context}</p>
                </div>
                
                <div className="analysis-card">
                  <h4>Connection Type</h4>
                  <div className="type-badge">{connection.llmAnalysis.connection_type || 'FOREIGN KEY'}</div>
                </div>
                
                <div className="analysis-card">
                  <h4>Join Strategy</h4>
                  <div className="strategy-badge">{connection.llmAnalysis.suggested_join_strategy || 'inner join'}</div>
                </div>
              </div>

              {/* Potential Issues */}
              {connection.llmAnalysis.potential_issues && connection.llmAnalysis.potential_issues.length > 0 && (
                <div className="issues-section">
                  <h4>⚠️ Potential Issues</h4>
                  <ul>
                    {connection.llmAnalysis.potential_issues.map((issue, index) => (
                      <li key={index}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Recommendations */}
              {connection.llmAnalysis.recommendations && connection.llmAnalysis.recommendations.length > 0 && (
                <div className="recommendations-section">
                  <h4>💡 Recommendations</h4>
                  <ul>
                    {connection.llmAnalysis.recommendations.map((rec, index) => (
                      <li key={index}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          {/* Action Question */}
          <div className="action-question">
            <p>
              Does this connection make sense for your data? 
              <span className="highlight">Click "Yes" to create the connection</span> or "Cancel" to skip it.
            </p>
          </div>
        </div>
        
        {/* Footer with buttons */}
        <div className="prompt-actions">
          <button className="cancel-button" onClick={handleCancel}>
            Cancel
          </button>
          <button className="confirm-button" onClick={handleYes}>
            Yes, Create Connection
          </button>
        </div>
        
        {/* Help tip */}
        <div className="prompt-help">
          <small>
            💡 <strong>Tip:</strong> The AI analyzes column names, data types, and patterns to suggest connections. 
            You can always review and modify connections later. Press <kbd>Esc</kbd> to close.
          </small>
        </div>
      </div>
    </div>
  );
};

export default ConnectionPrompt; 