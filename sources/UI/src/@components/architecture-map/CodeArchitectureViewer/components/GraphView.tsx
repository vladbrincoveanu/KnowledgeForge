import React from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
} from 'reactflow';

interface GraphViewProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: any;
  onEdgesChange: any;
  onNodeClick: any;
  onEdgeClick: any;
  nodeTypes: Record<string, any>;
  edgeTypes: Record<string, any>;
  selectedLevel: string;
  isLoading?: boolean;
  loadingText?: string | null;
}

export default function GraphView({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  onEdgeClick,
  nodeTypes,
  edgeTypes,
  selectedLevel,
  isLoading,
  loadingText,
}: GraphViewProps) {
  if (nodes.length === 0) {
    return (
      <main className="graph-container">
        <div className="empty-state">
          <p>{isLoading ? (loadingText || 'Scanning repository…') : 'No entities match the current filters'}</p>
        </div>
        {isLoading && (
          <div className="graph-loading-overlay" aria-live="polite">
            <div className="graph-loading-card">
              <div className="graph-loading-spinner" />
              <div className="graph-loading-title">Scanning</div>
              <div className="graph-loading-subtitle">
                {loadingText || 'Extracting architecture…'}
              </div>
            </div>
          </div>
        )}
      </main>
    );
  }

  return (
    <main className="graph-container">
      <div style={{ width: '100%', height: '100%' }}>
        <ReactFlow
          key={`${selectedLevel}-${nodes.length}-${edges.length}`}
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          elementsSelectable
          edgesFocusable
          fitView
          fitViewOptions={{
            padding: 0.15,
            minZoom: 0.5,
            maxZoom: 1.5,
          }}
          attributionPosition="bottom-left"
          minZoom={0.1}
          maxZoom={2.5}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#e0e0e0"
          />
          <Controls />
        </ReactFlow>
      </div>
      {isLoading && (
        <div className="graph-loading-overlay" aria-live="polite">
          <div className="graph-loading-card">
            <div className="graph-loading-spinner" />
            <div className="graph-loading-title">Scanning</div>
            <div className="graph-loading-subtitle">
              {loadingText || 'Extracting architecture…'}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
