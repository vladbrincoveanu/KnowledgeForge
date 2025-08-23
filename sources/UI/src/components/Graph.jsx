import React, { useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import './Graph.css';

const Graph = ({ data }) => {
  const graphRef = useRef();

  const handleNodeClick = useCallback((node) => {
    // You can add node click functionality here
    console.log('Clicked node:', node);
  }, []);

  const handleLinkClick = useCallback((link) => {
    // You can add link click functionality here
    console.log('Clicked link:', link);
  }, []);

  const nodeColor = useCallback((node) => {
    return node.type === 'file' ? '#007bff' : '#28a745';
  }, []);

  const nodeLabel = useCallback((node) => {
    return `${node.label}\n(${node.type})`;
  }, []);

  const linkLabel = useCallback((link) => {
    return link.label || 'Connection';
  }, []);

  const linkColor = useCallback(() => {
    return '#666';
  }, []);

  const linkWidth = useCallback(() => {
    return 2;
  }, []);

  return (
    <div className="graph-container">
      <div className="graph-header">
        <h3>Network Graph</h3>
        <div className="graph-stats">
          <span>{data.nodes.length} Files</span>
          <span>{data.links.length} Connections</span>
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
        </div>
      )}
    </div>
  );
};

export default Graph; 