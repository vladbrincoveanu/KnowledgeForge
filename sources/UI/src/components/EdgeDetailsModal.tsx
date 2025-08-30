import React from 'react';

import { useEffect } from 'react';
import './EdgeDetailsModal.css';

interface EdgeDetailsModalProps {
  edge: any;
  isOpen: boolean;
  onClose: () => void;
}

const EdgeDetailsModal: React.FC<EdgeDetailsModalProps> = ({ edge, isOpen, onClose }) => {
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = event => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => {
        document.removeEventListener('keydown', handleEscape);
      };
    }
  }, [isOpen, onClose]);

  if (!isOpen || !edge) return null;

  // Helper function to safely extract string values
  const safeString = value => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'object') {
      // If it's a node object, try to get the label or id
      if (value.label) return value.label;
      if (value.id) return value.id;
      return JSON.stringify(value);
    }
    return String(value);
  };

  // Normalize field names coming from backend graph-data
  const normalized = {
    source_collection: safeString(edge.source_collection || edge.source),
    target_collection: safeString(edge.target_collection || edge.target),
    source_column: safeString(edge.source_column || edge.columnA),
    target_column: safeString(edge.target_column || edge.columnB),
    confidence_score: edge.confidence_score || edge.confidence,
    llm_analysis: edge.llm_analysis || null,
    connection_type: safeString(edge.connection_type || edge.type),
    created_at: edge.created_at || edge.createdAt,
    merged_metadata: edge.merged_metadata || edge.mergedMetadata || null,
  };

  const getConfidenceColor = confidence => {
    if (confidence >= 0.9) return '#10b981';
    if (confidence >= 0.7) return '#f59e0b';
    return '#ef4444';
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <div className="edge-details-overlay" onClick={handleClose}>
      <div className="edge-details-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="edge-header">
          <div className="header-content">
            <h2>Connection Details</h2>
            <div className="connection-status">
              <span className="status-badge confirmed">✓ Confirmed</span>
              <span
                className="confidence-badge"
                style={{
                  backgroundColor: getConfidenceColor(
                    normalized.confidence_score || 0.95
                  ),
                }}
              >
                {Math.round((normalized.confidence_score || 0.95) * 100)}%
                CONFIDENCE
              </span>
            </div>
          </div>
          <button className="close-button" onClick={handleClose}>
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M18 6L6 18M6 6L18 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="edge-content">
          {/* Merged Metadata Overview */}
          {normalized.merged_metadata && (
            <div className="merged-metadata">
              <h3>Merged Metadata Overview</h3>
              <div className="metadata-summary">
                <div className="metadata-item">
                  <span className="label">Total Columns</span>
                  <span className="value">
                    {normalized.merged_metadata.total_columns}
                  </span>
                </div>
                <div className="metadata-item">
                  <span className="label">Shared Columns</span>
                  <span className="value">
                    {normalized.merged_metadata.shared_columns}
                  </span>
                </div>
                <div className="metadata-item">
                  <span className="label">Unique Columns</span>
                  <span className="value">
                    {normalized.merged_metadata.unique_columns}
                  </span>
                </div>
                <div className="metadata-item">
                  <span className="label">Connection Strength</span>
                  <span className="value">
                    {Math.round(
                      (normalized.merged_metadata.connection_strength ||
                        normalized.confidence_score ||
                        0.9) * 100
                    )}
                    %
                  </span>
                </div>
                <div className="metadata-item">
                  <span className="label">Merge Strategy</span>
                  <span className="value">
                    {normalized.merged_metadata.merge_strategy}
                  </span>
                </div>
                <div className="metadata-item">
                  <span className="label">Join Column</span>
                  <span className="value">
                    {normalized.merged_metadata.join_column}
                  </span>
                </div>
              </div>

              {normalized.merged_metadata.data_quality_metrics && (
                <div className="data-quality-metrics">
                  <h6>Data Quality Metrics</h6>
                  <div className="metrics-grid">
                    {Object.entries(
                      normalized.merged_metadata.data_quality_metrics
                    ).map(([k, v]) => (
                      <div key={k} className="metric-item">
                        <span className="metric-label">{k}</span>
                        <span className="metric-value">
                          {Math.round(v * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {normalized.merged_metadata.sample_data &&
                normalized.merged_metadata.sample_data.columns && (
                  <div className="sample-data">
                    <h6>Sample Merged Data</h6>
                    <div className="sample-table">
                      <table>
                        <thead>
                          <tr>
                            {normalized.merged_metadata.sample_data.columns.map(
                              (col, idx) => (
                                <th key={idx}>{col}</th>
                              )
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            normalized.merged_metadata.sample_data.rows || []
                          ).map((row, rIdx) => (
                            <tr key={rIdx}>
                              {row.map((cell, cIdx) => (
                                <td key={cIdx}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
            </div>
          )}
          {/* Connection Overview */}
          <div className="connection-overview">
            <div className="dataset-card">
              <div className="dataset-name">{normalized.source_collection}</div>
              <div className="column-pill">{normalized.source_column}</div>
            </div>

            <div className="connection-arrow">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M7 17L17 7M17 7H7M17 7V17"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <div className="dataset-card">
              <div className="dataset-name">{normalized.target_collection}</div>
              <div className="column-pill">{normalized.target_column}</div>
            </div>
          </div>

          {/* Connection Metadata */}
          <div className="connection-metadata">
            <div className="metadata-grid">
              <div className="metadata-item">
                <strong>Connection Type:</strong>
                <div className="type-badge">
                  {normalized.connection_type || 'FOREIGN_KEY'}
                </div>
              </div>
              <div className="metadata-item">
                <strong>Join Strategy:</strong>
                <div className="strategy-badge">
                  {safeString(edge.join_strategy || 'inner_join')}
                </div>
              </div>
              <div className="metadata-item">
                <strong>Created:</strong>
                <span>
                  {normalized.created_at
                    ? new Date(normalized.created_at).toLocaleDateString()
                    : 'Unknown'}
                </span>
              </div>
              <div className="metadata-item">
                <strong>Status:</strong>
                <span className="status-text">Active</span>
              </div>
            </div>
          </div>

          {/* AI Analysis (if available) */}
          {normalized.llm_analysis && (
            <div className="ai-analysis-section">
              <h3>AI Analysis</h3>

              <div className="analysis-grid">
                <div className="analysis-card">
                  <h4>Reasoning</h4>
                  <p>
                    {normalized.llm_analysis.reasoning ||
                      'AI analysis not available'}
                  </p>
                </div>

                <div className="analysis-card">
                  <h4>Business Context</h4>
                  <p>
                    {normalized.llm_analysis.business_context ||
                      'Context not available'}
                  </p>
                </div>

                <div className="analysis-card">
                  <h4>Connection Type</h4>
                  <div className="type-badge">
                    {normalized.llm_analysis.connection_type ||
                      normalized.connection_type ||
                      'FOREIGN_KEY'}
                  </div>
                </div>

                <div className="analysis-card">
                  <h4>Join Strategy</h4>
                  <div className="strategy-badge">
                    {safeString(
                      normalized.llm_analysis.suggested_join_strategy ||
                        edge.join_strategy ||
                        'inner_join'
                    )}
                  </div>
                </div>
              </div>

              {/* Potential Issues */}
              {normalized.llm_analysis.potential_issues &&
                normalized.llm_analysis.potential_issues.length > 0 && (
                  <div className="issues-section">
                    <h4>⚠️ Potential Issues</h4>
                    <ul>
                      {normalized.llm_analysis.potential_issues.map(
                        (issue, index) => (
                          <li key={index}>{issue}</li>
                        )
                      )}
                    </ul>
                  </div>
                )}

              {/* Recommendations */}
              {normalized.llm_analysis.recommendations &&
                normalized.llm_analysis.recommendations.length > 0 && (
                  <div className="recommendations-section">
                    <h4>💡 Recommendations</h4>
                    <ul>
                      {normalized.llm_analysis.recommendations.map(
                        (rec, index) => (
                          <li key={index}>{rec}</li>
                        )
                      )}
                    </ul>
                  </div>
                )}
            </div>
          )}

          {/* Connection Summary */}
          <div className="connection-summary">
            <h3>Connection Summary</h3>
            <p>
              This connection links <strong>{normalized.source_column}</strong>{' '}
              from <strong>{normalized.source_collection}</strong>
              to <strong>{normalized.target_column}</strong> from{' '}
              <strong>{normalized.target_collection}</strong>.
            </p>
            <p>
              The connection was confirmed with{' '}
              {Math.round((normalized.confidence_score || 0.95) * 100)}%
              confidence and is currently active in your data graph.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="edge-footer">
          <button className="secondary-button" onClick={handleClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default EdgeDetailsModal;
