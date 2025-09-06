import React from 'react';

import './NodeDetailsModal.scss';
import { GraphNode } from '../types';

interface NodeDetailsModalProps {
  node: GraphNode;
  isOpen: boolean;
  onClose: () => void;
}

const NodeDetailsModal: React.FC<NodeDetailsModalProps> = ({
  node,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !node) return null;

  const formatDataType = (dataType: unknown) => {
    if (typeof dataType === 'string') {
      return dataType.charAt(0).toUpperCase() + dataType.slice(1);
    }
    return 'Unknown';
  };

  const safeString = (value: unknown) => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  const _getConfidenceLabel = (confidence: number) => {
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
            <h3>📊 Entity Information</h3>
            <div className="info-grid">
              <div className="info-item">
                <span className="label">Entity Name:</span>
                <div className="value-with-tooltip">
                  <span className="value">{safeString(node.label)}</span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      The name of the data concept that AI identified in your dataset. This represents what the data represents (e.g., "product_id", "customer_name").
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Entity Type:</span>
                <div className="value-with-tooltip">
                  <span className="value">{safeString(node.entityType || node.type)}</span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      The category of data this represents: identifier (unique IDs), measurement (numbers/quantities), categorical (categories/labels), or geographic (locations).
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Confidence:</span>
                <div className="value-with-tooltip">
                  <span className="value">
                    <span className={`confidence-badge confidence-${_getConfidenceLabel(node.confidence || 0).toLowerCase().replace(' ', '-')}`}>
                      {Math.round((node.confidence || 0) * 100)}% ({_getConfidenceLabel(node.confidence || 0)})
                    </span>
                  </span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      How certain the AI is about this classification. Higher percentages mean the AI is more confident this is correctly identified.
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Source Columns:</span>
                <div className="value-with-tooltip">
                  <span className="value">
                    {node.metadata?.sourceColumns?.length || 0} columns
                  </span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      The specific columns in your CSV file where this entity was found. Shows which data columns the AI analyzed to identify this concept.
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Source Value:</span>
                <div className="value-with-tooltip">
                  <span className="value">
                    {node.metadata?.sourceValue && node.metadata.sourceValue !== 'N/A' 
                      ? safeString(node.metadata.sourceValue)
                      : 'Not available - entity extracted from column structure'
                    }
                  </span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      An example actual value from your data that the AI used to identify this entity. Shows what the data looks like in practice.
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Source File:</span>
                <div className="value-with-tooltip">
                  <span className="value">{safeString(node.metadata?.sourceFile || 'Unknown')}</span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      The original CSV file where this entity was discovered. Shows which file the AI analyzed to identify this data concept.
                    </div>
                  </div>
                </div>
              </div>
              <div className="info-item">
                <span className="label">Entity ID:</span>
                <div className="value-with-tooltip">
                  <span className="value">{safeString(node.id)}</span>
                  <div className="tooltip">
                    <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                    <div className="tooltip-content">
                      A unique identifier for this entity in the system. Used internally to track and reference this specific data concept.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {node.metadata?.sourceColumns && node.metadata.sourceColumns.length > 0 && (
            <div className="source-columns-section">
              <div className="section-header-with-tooltip">
                <h3>📋 Source Columns</h3>
                <div className="tooltip">
                  <img src="/src/assets/info.svg" alt="info" className="tooltip-icon" />
                  <div className="tooltip-content">
                    These are the actual column names from your CSV file where this entity was found. Click on any column to see more details about the data in that column.
                  </div>
                </div>
              </div>
              <div className="source-columns-list">
                {node.metadata.sourceColumns.map((column: string, index: number) => (
                  <div key={index} className="source-column-item">
                    <span className="column-name">{column}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {node.metadata?.attributes && Object.keys(node.metadata.attributes).length > 0 && (
            <div className="attributes-section">
              <h3>🔧 Entity Attributes</h3>
              <div className="attributes-grid">
                {Object.entries(node.metadata.attributes).map(([key, value]) => (
                  <div key={key} className="attribute-item">
                    <span className="attribute-key">{key}:</span>
                    <span className="attribute-value">{safeString(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {node.columns && Object.keys(node.columns).length > 0 && (
            <div className="columns-section">
              <h3>📊 Column Statistics</h3>
              <div className="columns-grid">
                {Object.entries(node.columns || {}).map(
                  ([columnName, columnData]: [string, any]) => (
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
                                .map((value: unknown, index: number) => (
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

          {(!node.metadata?.sourceColumns || node.metadata.sourceColumns.length === 0) && 
           (!node.metadata?.attributes || Object.keys(node.metadata.attributes).length === 0) && 
           (!node.columns || Object.keys(node.columns).length === 0) && (
            <div className="no-metadata">
              <p>⚠️ No detailed metadata available for this entity.</p>
              <p>This entity was extracted from your data but doesn't have additional metadata stored in PostgreSQL.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodeDetailsModal;
