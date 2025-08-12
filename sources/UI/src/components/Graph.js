import React, { useRef, useCallback, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import EdgeDetailsModal from './EdgeDetailsModal';
import NodeDetailsModal from './NodeDetailsModal';
import './Graph.css';

const Graph = ({ data, onEdgeClick, onEdgeConfirm, onEdgeReject }) => {
  const graphRef = useRef();
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [showEdgeModal, setShowEdgeModal] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [showNodeModal, setShowNodeModal] = useState(false);

  const handleNodeClick = useCallback((node) => {
    console.log('Clicked node:', node);
    // Clear edge selection when clicking on a node
    setSelectedEdge(null);
    setShowEdgeModal(false);
    
    // Set node selection and show modal
    setSelectedNode(node);
    setShowNodeModal(true);
  }, []);

  const handleLinkClick = useCallback((link) => {
    console.log('Clicked link:', link);
    setSelectedEdge(link);
    setShowEdgeModal(true);
    
    // Call parent callback if provided
    if (onEdgeClick) {
      onEdgeClick(link);
    }
  }, [onEdgeClick]);

  const nodeColor = useCallback((node) => {
    return node.type === 'file' ? '#007bff' : '#28a745';
  }, []);

  const nodeLabel = useCallback((node) => {
    return `${node.label}\n(${node.type})`;
  }, []);

  const linkLabel = useCallback((link) => {
    return link.label || 'Connection';
  }, []);

  const linkColor = useCallback((link) => {
    // Color based on connection strength/confidence
    if (link.confidence >= 0.9) return '#28a745'; // High confidence - green
    if (link.confidence >= 0.7) return '#ffc107'; // Medium confidence - yellow
    return '#dc3545'; // Low confidence - red
  }, []);

  const linkWidth = useCallback((link) => {
    // Width based on connection strength
    if (link.confidence >= 0.9) return 4;
    if (link.confidence >= 0.7) return 3;
    return 2;
  }, []);

  const closeEdgeModal = () => {
    setShowEdgeModal(false);
    setSelectedEdge(null);
  };

  const closeNodeModal = () => {
    setShowNodeModal(false);
    setSelectedNode(null);
  };





  return (
    <div className="graph-container">
      <div className="graph-header">
        <h3>AI-Powered Visual Knowledge Discovery</h3>
        <div className="graph-stats">
          <span>{data.nodes.length} Files</span>
          <span>{data.links.length} AI-Detected Connections</span>
          {selectedEdge && (
            <span className="selected-edge">
              Selected: {selectedEdge.columnA} ↔ {selectedEdge.columnB}
            </span>
          )}
        </div>
        <div className="discovery-insights">
          <div className="insight-item">
            <span className="insight-icon">🔍</span>
            <span>AI analyzes patterns in your data</span>
          </div>
          <div className="insight-item">
            <span className="insight-icon">💡</span>
            <span>Discover hidden relationships</span>
          </div>
          <div className="insight-item">
            <span className="insight-icon">✅</span>
            <span>Validate connections visually</span>
          </div>
        </div>
      </div>
      
      <div className="graph-visualization">
        {data.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={data}
            nodeLabel={nodeLabel}
            linkLabel={linkLabel}
            nodeColor={nodeColor}
            linkColor={linkColor}
            linkWidth={linkWidth}
            onNodeClick={handleNodeClick}
            onLinkClick={handleLinkClick}
            nodeRelSize={8}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            linkCurvature={0.1}
            cooldownTicks={100}
            onEngineStop={() => graphRef.current.zoomToFit(400)}
            backgroundColor="#ffffff"
            width={800}
            height={600}
          />
        ) : (
          <div className="empty-graph">
            <div className="empty-icon">📊</div>
            <h4>No Files Uploaded</h4>
            <p>Upload CSV files to see the network graph visualization</p>
          </div>
        )}
      </div>
      
      {data.nodes.length > 0 && (
        <div className="graph-controls">
          <button 
            className="btn-control"
            onClick={() => graphRef.current.zoomToFit(400)}
          >
            Fit to View
          </button>
          <button 
            className="btn-control"
            onClick={() => graphRef.current.centerAt(0, 0, 1000)}
          >
            Center
          </button>
          <button 
            className="btn-control"
            onClick={() => {
              setSelectedEdge(null);
            }}
          >
            Clear Selection
          </button>
        </div>
      )}

      {/* Edge Details Modal */}
      {showEdgeModal && selectedEdge && (
        <EdgeDetailsModal
          key={`edge-modal-${selectedEdge.id}`}
          edge={selectedEdge}
          isOpen={showEdgeModal}
          onClose={closeEdgeModal}
        />
      )}

      {/* Node Details Modal */}
      {showNodeModal && selectedNode && (
        <NodeDetailsModal
          key={`node-modal-${selectedNode.id}`}
          node={selectedNode}
          isOpen={showNodeModal}
          onClose={closeNodeModal}
        />
      )}
    </div>
  );
};

export default Graph; 