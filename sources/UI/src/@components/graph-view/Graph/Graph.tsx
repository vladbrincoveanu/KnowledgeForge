import React, { useRef, useCallback, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import EdgeDetailsModal from '../EdgeDetailsModal/EdgeDetailsModal';
import NodeDetailsModal from '../NodeDetailsModal/NodeDetailsModal';
import './Graph.scss';
import { GraphData, GraphLink, GraphNode } from '../../../types';

interface GraphProps {
  data: GraphData;
  onEdgeClick: (edge: GraphLink) => void;
}

const Graph: React.FC<GraphProps> = ({ data, onEdgeClick }) => {
  const graphRef = useRef<any>();
  const [selectedEdge, setSelectedEdge] = useState<GraphLink | null>(null);
  const [showEdgeModal, setShowEdgeModal] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showNodeModal, setShowNodeModal] = useState(false);

  // Debug logging
  console.log('Graph component received data:', data);
  console.log('Graph nodes count:', data.nodes.length);
  console.log('Graph links count:', data.links.length);

  // Validate data structure
  const isValidData = data && Array.isArray(data.nodes) && Array.isArray(data.links);
  console.log('Graph data is valid:', isValidData);

  // Debug: Check for orphaned links
  if (data.links && data.links.length > 0) {
    const nodeIds = new Set(data.nodes.map(n => n.id));
    const orphanedLinks = data.links.filter(link => 
      !nodeIds.has(link.source) || !nodeIds.has(link.target)
    );
    if (orphanedLinks.length > 0) {
      console.warn('Found orphaned links:', orphanedLinks);
    }
    
    // Log valid links
    const validLinks = data.links.filter(link => 
      nodeIds.has(link.source) && nodeIds.has(link.target)
    );
    console.log('Valid links for graph:', validLinks);
  }

  const handleNodeClick = useCallback((node: GraphNode) => {
    console.log('Clicked node:', node);
    // Clear edge selection when clicking on a node
    setSelectedEdge(null);
    setShowEdgeModal(false);

    // Set node selection and show modal
    setSelectedNode(node);
    setShowNodeModal(true);
  }, []);

  const handleLinkClick = useCallback(
    (link: GraphLink) => {
      console.log('Clicked link:', link);
      setSelectedEdge(link);
      setShowEdgeModal(true);

      // Call parent callback if provided
      if (onEdgeClick) {
        onEdgeClick(link);
      }
    },
    [onEdgeClick]
  );

  const nodeColor = useCallback((node: GraphNode) => {
    // Simple single color for all nodes
    return '#007bff'; // Blue
  }, []);

  const nodeLabel = useCallback((node: GraphNode) => {
    return `${node.label}\n(${node.type})`;
  }, []);

  const linkLabel = useCallback((link: GraphLink) => {
    return link.label || 'Connection';
  }, []);

  const linkColor = useCallback((link: GraphLink) => {
    // Color based on connection strength/confidence
    const confidence = link.confidence || 0;
    console.log('Link color for:', link.id, 'confidence:', confidence);
    if (confidence >= 0.9) return '#28a745'; // High confidence - green
    if (confidence >= 0.7) return '#fd7e14'; // Medium confidence - orange
    if (confidence >= 0.5) return '#ffc107'; // Lower confidence - yellow
    return '#dc3545'; // Low confidence - red
  }, []);

  const linkWidth = useCallback((link: GraphLink) => {
    // Width based on connection strength
    const confidence = link.confidence || 0;
    console.log('Link width for:', link.id, 'confidence:', confidence);
    if (confidence >= 0.9) return 6;
    if (confidence >= 0.7) return 4;
    if (confidence >= 0.5) return 3;
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
        
        <div className="graph-legend">
          <div className="legend-section">
            <h4>Link Confidence:</h4>
            <div className="legend-items">
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#28a745' }}></span>
                <span>High (&gt;=90%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#fd7e14' }}></span>
                <span>Medium (&gt;=70%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#ffc107' }}></span>
                <span>Lower (&gt;=50%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#dc3545' }}></span>
                <span>Low (&lt;50%)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="graph-visualization">
        {!isValidData ? (
          <div className="empty-graph">
            <div className="empty-icon">⚠️</div>
            <h4>Invalid Graph Data</h4>
            <p>The graph data structure is invalid. Please check the console for details.</p>
          </div>
                ) : data.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={{
              nodes: data.nodes,
              links: data.links.filter(link => {
                // ForceGraph2D might be converting string IDs to objects
                // Let's ensure we're working with string IDs
                const sourceId = typeof link.source === 'object' && link.source !== null ? (link.source as any).id : String(link.source);
                const targetId = typeof link.target === 'object' && link.target !== null ? (link.target as any).id : String(link.target);
                
                console.log('Checking link:', link);
                console.log('Original source:', link.source, 'type:', typeof link.source);
                console.log('Original target:', link.target, 'type:', typeof link.target);
                console.log('Processed sourceId:', sourceId);
                console.log('Processed targetId:', targetId);
                
                const sourceExists = data.nodes.some(node => {
                  const nodeId = String(node.id);
                  const matches = nodeId === sourceId;
                  console.log('Comparing node ID:', nodeId, 'with sourceId:', sourceId, 'matches:', matches);
                  return matches;
                });
                const targetExists = data.nodes.some(node => {
                  const nodeId = String(node.id);
                  const matches = nodeId === targetId;
                  console.log('Comparing node ID:', nodeId, 'with targetId:', targetId, 'matches:', matches);
                  return matches;
                });
                
                const isValid = sourceExists && targetExists;
                if (!isValid) {
                  console.warn(`Invalid link: ${sourceId} -> ${targetId}`);
                  console.warn('Source exists:', sourceExists, 'Target exists:', targetExists);
                } else {
                  console.log(`Valid link: ${sourceId} -> ${targetId}`);
                }
                return isValid;
              })
            }}
            onLinkHover={(link) => {
              console.log('Link hovered:', link);
            }}
            onNodeHover={(node) => {
              console.log('Node hovered:', node);
            }}

            nodeLabel={nodeLabel}
            linkLabel={linkLabel}
            nodeColor={nodeColor}
            linkColor={linkColor}
            linkWidth={linkWidth}
            onNodeClick={handleNodeClick}
            onLinkClick={handleLinkClick}
            nodeRelSize={12}
            linkDirectionalArrowLength={8}
            linkDirectionalArrowRelPos={1}
            linkCurvature={0.2}
            cooldownTicks={200}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            onEngineStop={() => {
              console.log('Graph engine stopped, zooming to fit');
              // Add a small delay to ensure the graph has settled
              setTimeout(() => {
                graphRef.current?.zoomToFit(400, 50);
              }, 100);
            }}
            backgroundColor="#ffffff"
            width={800}
            height={600}
          />
        ) : (
          <div className="empty-graph">
            <div className="empty-icon">📊</div>
            <h4>No Graph Data Available</h4>
            <p>Complete an ontology extraction to see the network graph visualization</p>
            <p>This graph shows the same entities and relationships as the Ontology Results section</p>
            <p>Current data: {data.nodes.length} nodes, {data.links.length} links</p>
          </div>
        )}
      </div>

      {data.nodes.length > 0 && (
        <div className="graph-controls">
          <button
            className="btn-control"
            onClick={() => graphRef.current?.zoomToFit(400)}
          >
            Fit to View
          </button>
          <button
            className="btn-control"
            onClick={() => graphRef.current?.centerAt(0, 0, 1000)}
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
      {selectedEdge && (
        <EdgeDetailsModal
          key={`edge-modal-${selectedEdge.id || 'default'}`}
          edge={selectedEdge}
          isOpen={showEdgeModal}
          onClose={closeEdgeModal}
        />
      )}

      {/* Node Details Modal */}
      {selectedNode && (
        <NodeDetailsModal
          key={`node-modal-${selectedNode.id || 'default'}`}
          node={selectedNode}
          isOpen={showNodeModal}
          onClose={closeNodeModal}
        />
      )}
    </div>
  );
};

export default Graph;
