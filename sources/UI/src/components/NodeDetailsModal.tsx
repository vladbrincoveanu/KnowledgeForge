import React from 'react';

import './NodeDetailsModal.css';

interface NodeDetailsModalProps {
  node: any;
  isOpen: boolean;
  onClose: () => void;
}

const NodeDetailsModal: React.FC<NodeDetailsModalProps> = ({ node, isOpen, onClose }) => {
  if (!isOpen || !node) return null;

  const formatDataType = dataType => {
    if (typeof dataType === 'string') {
      return dataType.charAt(0).toUpperCase() + dataType.slice(1);
    }
    return 'Unknown';
  };

  const safeString = value => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  const _getConfidenceLabel = confidence => {
    if (confidence >= 0.9) return 'Very High';
    if (confidence >= 0.7) return 'High';
    if (confidence >= 0.5) return 'Medium';
    return 'Low';
  };

  return (
    <div className="node-details-modal-overlay" onClick={onClose}>
      <div className="node-details-modal" onClick={e => e.stopPropagation()}>
        <div className="node-details-header">
          <h2>📁 {node.label}</h2>
          <button className="close-button" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="node-details-content">
          <div className="node-info-section">
            <h3>📊 File Information</h3>
            <div className="info-grid">
              <div className="info-item">
                <span className="label">File Type:</span>
                <span className="value">{safeString(node.type)}</span>
              </div>
              <div className="info-item">
                <span className="label">Total Columns:</span>
                <span className="value">
                  {safeString(node.metadata?.columns || 0)}
                </span>
              </div>
              <div className="info-item">
                <span className="label">Upload Date:</span>
                <span className="value">
                  {node.metadata?.uploadDate
                    ? new Date(node.metadata.uploadDate).toLocaleDateString()
                    : 'Unknown'}
                </span>
              </div>
            </div>
          </div>

          {node.columns && Object.keys(node.columns).length > 0 && (
            <div className="columns-section">
              <h3>📋 Column Details</h3>
              <div className="columns-grid">
                {Object.entries(node.columns).map(
                  ([columnName, columnData]) => (
                    <div key={columnName} className="column-card">
                      <div className="column-header">
                        <h4>{columnName}</h4>
                        <span className="data-type-badge">
                          {formatDataType(columnData.data_type)}
                        </span>
                      </div>

                      <div className="column-stats">
                        <div className="stat-item">
                          <span className="stat-label">Position:</span>
                          <span className="stat-value">
                            {safeString(columnData.position)}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Nullable:</span>
                          <span className="stat-value">
                            {columnData.nullable ? 'Yes' : 'No'}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Unique Values:</span>
                          <span className="stat-value">
                            {safeString(columnData.unique_count)}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Null Count:</span>
                          <span className="stat-value">
                            {safeString(columnData.null_count)}
                          </span>
                        </div>
                        {columnData.min_value !== null && (
                          <div className="stat-item">
                            <span className="stat-label">Min Value:</span>
                            <span className="stat-value">
                              {safeString(columnData.min_value)}
                            </span>
                          </div>
                        )}
                        {columnData.max_value !== null && (
                          <div className="stat-item">
                            <span className="stat-label">Max Value:</span>
                            <span className="stat-value">
                              {safeString(columnData.max_value)}
                            </span>
                          </div>
                        )}
                        {columnData.max_length && (
                          <div className="stat-item">
                            <span className="stat-label">Max Length:</span>
                            <span className="stat-value">
                              {safeString(columnData.max_length)}
                            </span>
                          </div>
                        )}
                      </div>

                      {columnData.sample_values &&
                        columnData.sample_values.length > 0 && (
                          <div className="sample-values">
                            <span className="sample-label">Sample Values:</span>
                            <div className="sample-list">
                              {columnData.sample_values
                                .slice(0, 5)
                                .map((value, index) => (
                                  <span key={index} className="sample-value">
                                    {String(value)}
                                  </span>
                                ))}
                              {columnData.sample_values.length > 5 && (
                                <span className="sample-more">
                                  +{columnData.sample_values.length - 5} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {(!node.columns || Object.keys(node.columns).length === 0) && (
            <div className="no-columns">
              <p>⚠️ No column metadata available for this file.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodeDetailsModal;
