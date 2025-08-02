import React from 'react';
import './ConnectionPrompt.css';

const ConnectionPrompt = ({ connection, onResponse }) => {
  const handleYes = () => {
    onResponse(true, connection);
  };

  const handleNo = () => {
    onResponse(false, connection);
  };

  const confidenceColor = connection.confidence > 0.8 ? '#28a745' : 
                         connection.confidence > 0.6 ? '#ffc107' : '#dc3545';

  const confidenceText = connection.confidence > 0.8 ? 'High' :
                        connection.confidence > 0.6 ? 'Medium' : 'Low';

  return (
    <div className="connection-prompt-overlay">
      <div className="connection-prompt">
        <div className="prompt-header">
          <h3>🔗 Potential Connection Found</h3>
          <div className="confidence-badge" style={{ backgroundColor: confidenceColor }}>
            {confidenceText} Confidence ({Math.round(connection.confidence * 100)}%)
          </div>
        </div>
        
        <div className="prompt-content">
          <div className="connection-details">
            <div className="file-section">
              <h4>📄 {connection.fileA}</h4>
              <div className="column-highlight">
                <span className="column-name">{connection.columnA}</span>
              </div>
            </div>
            
            <div className="connection-arrow">
              <span>↔</span>
            </div>
            
            <div className="file-section">
              <h4>📄 {connection.fileB}</h4>
              <div className="column-highlight">
                <span className="column-name">{connection.columnB}</span>
              </div>
            </div>
          </div>
          
          <div className="prompt-question">
            <p>
              <strong>Is there a connection between</strong>
              <br />
              <span className="highlight">"{connection.columnA}"</span> in <strong>{connection.fileA}</strong>
              <br />
              <span>and</span>
              <br />
              <span className="highlight">"{connection.columnB}"</span> in <strong>{connection.fileB}</strong>?
            </p>
          </div>
        </div>
        
        <div className="prompt-actions">
          <button className="btn-yes" onClick={handleYes}>
            ✅ Yes, Connect Them
          </button>
          <button className="btn-no" onClick={handleNo}>
            ❌ No, Skip This
          </button>
        </div>
        
        <div className="prompt-help">
          <small>
            💡 This helps build relationships between your data files. 
            Connected files will be linked in the network graph.
          </small>
        </div>
      </div>
    </div>
  );
};

export default ConnectionPrompt; 