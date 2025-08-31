import React, { useState, useEffect, useRef } from 'react';
import {
  SemanticQuery,
  QueryNode,
  QueryEdge,
  NodeType,
  EdgeType,
  Insight,
} from '@/types';
import './VisualQueryBuilder.css';

interface ExportFormat {
  value: string;
  label: string;
  icon: string;
}

const VisualQueryBuilder: React.FC = () => {
  const [queries, setQueries] = useState<SemanticQuery[]>([]);
  const [currentQuery, setCurrentQuery] = useState<SemanticQuery | null>(null);
  const [nodes, setNodes] = useState<QueryNode[]>([]);
  const [edges, setEdges] = useState<QueryEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showNodePanel, setShowNodePanel] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);
  const [naturalLanguage, setNaturalLanguage] = useState('');
  const [insights, setInsights] = useState<Insight[]>([]);
  const [exportContent, setExportContent] = useState('');
  const [exportFormat, setExportFormat] = useState<string>('sql');

  const canvasRef = useRef<HTMLDivElement>(null);
  const nodeIdCounter = useRef(0);
  const edgeIdCounter = useRef(0);

  const nodeTypes: (NodeType & { color: string })[] = [
    {
      type: 'table',
      label: 'Table',
      icon: '📊',
      description: 'Database table',
      color: '#4CAF50',
    },
    {
      type: 'field',
      label: 'Field',
      icon: '🔍',
      description: 'Table field/column',
      color: '#2196F3',
    },
    {
      type: 'aggregation',
      label: 'Aggregation',
      icon: '📈',
      description: 'Aggregation function',
      color: '#FF9800',
    },
    {
      type: 'filter',
      label: 'Filter',
      icon: '🔒',
      description: 'Filter condition',
      color: '#F44336',
    },
    {
      type: 'join',
      label: 'Join',
      icon: '🔗',
      description: 'Join operation',
      color: '#9C27B0',
    },
    {
      type: 'subquery',
      label: 'Subquery',
      icon: '📋',
      description: 'Subquery',
      color: '#607D8B',
    },
  ];

  const edgeTypes: (EdgeType & { color: string })[] = [
    {
      type: 'select',
      label: 'SELECT',
      description: 'Select operation',
      color: '#4CAF50',
    },
    {
      type: 'where',
      label: 'WHERE',
      description: 'Where clause',
      color: '#F44336',
    },
    {
      type: 'join',
      label: 'JOIN',
      description: 'Join clause',
      color: '#2196F3',
    },
    {
      type: 'group_by',
      label: 'GROUP BY',
      description: 'Group by clause',
      color: '#FF9800',
    },
    {
      type: 'order_by',
      label: 'ORDER BY',
      description: 'Order by clause',
      color: '#9C27B0',
    },
    {
      type: 'having',
      label: 'HAVING',
      description: 'Having clause',
      color: '#607D8B',
    },
  ];

  const exportFormats: ExportFormat[] = [
    { value: 'sql', label: 'SQL', icon: '💾' },
    { value: 'python', label: 'Python', icon: '🐍' },
    { value: 'r', label: 'R', icon: '📊' },
    { value: 'natural_language', label: 'Natural Language', icon: '💬' },
    { value: 'json', label: 'JSON', icon: '📄' },
  ];

  useEffect(() => {
    // Load existing queries from localStorage or API
    const savedQueries = localStorage.getItem('semanticQueries');
    if (savedQueries) {
      setQueries(JSON.parse(savedQueries));
    }
  }, []);

  useEffect(() => {
    // Save queries to localStorage
    localStorage.setItem('semanticQueries', JSON.stringify(queries));
  }, [queries]);

  const createNewQuery = () => {
    const queryName = prompt('Enter query name:');
    if (queryName) {
      const newQuery: SemanticQuery = {
        id: `query_${Date.now()}`,
        name: queryName,
        description: '',
        nodes: [],
        edges: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      setQueries([...queries, newQuery]);
      setCurrentQuery(newQuery);
      setNodes([]);
      setEdges([]);
    }
  };

  const addNode = (nodeType: string, x: number, y: number) => {
    const newNode: QueryNode = {
      id: `node_${nodeIdCounter.current++}`,
      name: `${nodeType}_${nodeIdCounter.current}`,
      node_type: nodeType as QueryNode['node_type'],
      metadata: {},
      position: { x, y },
      properties: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    setNodes([...nodes, newNode]);
    setShowNodePanel(false);
  };

  const addEdge = (sourceId: string, targetId: string, edgeType: string) => {
    const newEdge: QueryEdge = {
      id: `edge_${edgeIdCounter.current++}`,
      source_node_id: sourceId,
      target_node_id: targetId,
      edge_type: edgeType as QueryEdge['edge_type'],
      properties: {},
      conditions: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    setEdges([...edges, newEdge]);
  };

  const handleNodeDragStart = (e: React.MouseEvent, nodeId: string) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
    setSelectedNode(nodeId);
  };

  const handleNodeDrag = (e: React.MouseEvent) => {
    if (isDragging && selectedNode) {
      const deltaX = e.clientX - dragStart.x;
      const deltaY = e.clientY - dragStart.y;

      setNodes(
        nodes.map(node =>
          node.id === selectedNode
            ? {
                ...node,
                position: {
                  x: node.position.x + deltaX,
                  y: node.position.y + deltaY,
                },
              }
            : node
        )
      );

      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleNodeDragEnd = () => {
    setIsDragging(false);
    setSelectedNode(null);
  };

  const handleNodeClick = (nodeId: string) => {
    setSelectedNode(nodeId);
    setSelectedEdge(null);
  };

  const handleEdgeClick = (edgeId: string) => {
    setSelectedEdge(edgeId);
    setSelectedNode(null);
  };

  const handleCanvasClick = (e: React.MouseEvent) => {
    if (e.target === canvasRef.current) {
      setSelectedNode(null);
      setSelectedEdge(null);
    }
  };

  const handleNodeDoubleClick = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      const newName = prompt('Enter new name:', node.name);
      if (newName) {
        setNodes(
          nodes.map(n => (n.id === nodeId ? { ...n, name: newName } : n))
        );
      }
    }
  };

  const deleteSelectedNode = () => {
    if (selectedNode) {
      setNodes(nodes.filter(n => n.id !== selectedNode));
      setEdges(
        edges.filter(
          e =>
            e.source_node_id !== selectedNode &&
            e.target_node_id !== selectedNode
        )
      );
      setSelectedNode(null);
    }
  };

  const deleteSelectedEdge = () => {
    if (selectedEdge) {
      setEdges(edges.filter(e => e.id !== selectedEdge));
      setSelectedEdge(null);
    }
  };

  const _connectNodes = () => {
    if (selectedNode && selectedEdge) {
      const edge = edges.find(e => e.id === selectedEdge);
      if (edge) {
        const edgeType = prompt(
          'Enter edge type (select, where, join, etc.):',
          edge.edge_type
        );
        if (edgeType) {
          addEdge(selectedNode, edge.target_node_id, edgeType);
        }
      }
    }
  };

  const translateToNaturalLanguage = async () => {
    try {
      // In a real implementation, this would call the API
      const queryDescription = createQueryDescription();
      setNaturalLanguage(`This query ${queryDescription}`);
    } catch (error) {
      console.error('Error translating query:', error);
      setNaturalLanguage('Error translating query to natural language');
    }
  };

  const generateInsights = async () => {
    try {
      // In a real implementation, this would call the API
      const mockInsights = [
        {
          insight_type: 'business_analysis',
          description:
            'This query provides valuable customer segmentation data',
          confidence_score: 0.85,
          recommendations: [
            'Consider adding date filters',
            'Include more customer attributes',
          ],
        },
      ];
      setInsights(mockInsights);
    } catch (error) {
      console.error('Error generating insights:', error);
    }
  };

  const exportQuery = async () => {
    try {
      // In a real implementation, this would call the API
      let content = '';

      switch (exportFormat) {
        case 'sql':
          content = generateSQL();
          break;
        case 'python':
          content = generatePython();
          break;
        case 'r':
          content = generateR();
          break;
        case 'natural_language':
          content = createQueryDescription();
          break;
        case 'json':
          content = JSON.stringify({ nodes, edges }, null, 2);
          break;
        default:
          content = 'Unsupported format';
      }

      setExportContent(content);
    } catch (error) {
      console.error('Error exporting query:', error);
      setExportContent('Error exporting query');
    }
  };

  const createQueryDescription = () => {
    if (nodes.length === 0) return 'has no nodes';

    const tableNodes = nodes.filter(n => n.node_type === 'table');
    const fieldNodes = nodes.filter(n => n.node_type === 'field');

    let description = `selects ${fieldNodes.length > 0 ? fieldNodes.map(n => n.name).join(', ') : 'all fields'}`;

    if (tableNodes.length > 0) {
      description += ` from ${tableNodes.map(n => n.name).join(', ')}`;
    }

    if (edges.length > 0) {
      description += ` with ${edges.length} connections`;
    }

    return description;
  };

  const generateSQL = () => {
    const tableNodes = nodes.filter(n => n.node_type === 'table');
    const fieldNodes = nodes.filter(n => n.node_type === 'field');

    let sql = 'SELECT ';

    if (fieldNodes.length > 0) {
      sql += fieldNodes.map(n => n.name).join(', ');
    } else {
      sql += '*';
    }

    if (tableNodes.length > 0) {
      sql += ` FROM ${tableNodes.map(n => n.name).join(', ')}`;
    }

    sql += ';';
    return sql;
  };

  const generatePython = () => {
    const tableNodes = nodes.filter(n => n.node_type === 'table');
    const fieldNodes = nodes.filter(n => n.node_type === 'field');

    let python = 'import pandas as pd\n\n';

    if (tableNodes.length > 0) {
      python += `# Load data\n`;
      tableNodes.forEach(table => {
        python += `${table.name.toLowerCase()}_df = pd.read_csv('${table.name.toLowerCase()}.csv')\n`;
      });
      python += '\n';
    }

    if (fieldNodes.length > 0 && tableNodes.length > 0) {
      python += `# Select columns\n`;
      python += `columns = [${fieldNodes.map(n => `'${n.name}'`).join(', ')}]\n`;
      python += `result = ${tableNodes[0].name.toLowerCase()}_df[columns]\n`;
    }

    python += '\nprint(result.head())';
    return python;
  };

  const generateR = () => {
    const tableNodes = nodes.filter(n => n.node_type === 'table');
    const fieldNodes = nodes.filter(n => n.node_type === 'field');

    let r = '';

    if (tableNodes.length > 0) {
      r += `# Load data\n`;
      tableNodes.forEach(table => {
        r += `${table.name.toLowerCase()}_df <- read.csv('${table.name.toLowerCase()}.csv')\n`;
      });
      r += '\n';
    }

    if (fieldNodes.length > 0 && tableNodes.length > 0) {
      r += `# Select columns\n`;
      r += `columns <- c(${fieldNodes.map(n => `'${n.name}'`).join(', ')})\n`;
      r += `result <- ${tableNodes[0].name.toLowerCase()}_df[, columns]\n`;
    }

    r += '\nhead(result)';
    return r;
  };

  const saveQuery = () => {
    if (currentQuery) {
      const updatedQuery = {
        ...currentQuery,
        nodes,
        edges,
        updated_at: new Date().toISOString(),
      };

      setQueries(
        queries.map(q => (q.id === currentQuery.id ? updatedQuery : q))
      );

      setCurrentQuery(updatedQuery);
    }
  };

  return (
    <div className="visual-query-builder">
      <div className="toolbar">
        <button onClick={createNewQuery} className="btn btn-primary">
          🆕 New Query
        </button>
        <button onClick={saveQuery} className="btn btn-secondary">
          💾 Save Query
        </button>
        <button onClick={translateToNaturalLanguage} className="btn btn-info">
          🤖 Translate
        </button>
        <button onClick={generateInsights} className="btn btn-warning">
          💡 Insights
        </button>
        <button
          onClick={() => setShowExportPanel(true)}
          className="btn btn-success"
        >
          📤 Export
        </button>

        <select
          value={currentQuery?.id || ''}
          onChange={e => {
            const query = queries.find(q => q.id === e.target.value);
            setCurrentQuery(query);
            if (query) {
              setNodes(query.nodes || []);
              setEdges(query.edges || []);
            }
          }}
          className="query-selector"
        >
          <option value="">Select Query</option>
          {queries.map(q => (
            <option key={q.id} value={q.id}>
              {q.name}
            </option>
          ))}
        </select>
      </div>

      <div className="main-content">
        <div className="sidebar">
          <div className="node-palette">
            <h3>📦 Node Types</h3>
            {nodeTypes.map(nodeType => (
              <div
                key={nodeType.type}
                className="node-type"
                style={{ borderColor: nodeType.color }}
                onClick={() => setShowNodePanel(true)}
                draggable
                onDragStart={e => {
                  e.dataTransfer.setData('nodeType', nodeType.type);
                }}
              >
                <span className="node-icon">{nodeType.icon}</span>
                <span className="node-label">{nodeType.label}</span>
              </div>
            ))}
          </div>

          <div className="edge-palette">
            <h3>🔗 Edge Types</h3>
            {edgeTypes.map(edgeType => (
              <div
                key={edgeType.type}
                className="edge-type"
                style={{ borderColor: edgeType.color }}
              >
                <span className="edge-label">{edgeType.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div
          className="canvas-container"
          ref={canvasRef}
          onClick={handleCanvasClick}
          onMouseMove={handleNodeDrag}
          onMouseUp={handleNodeDragEnd}
        >
          <svg className="canvas" width="100%" height="100%">
            {/* Render edges */}
            {edges.map(edge => {
              const sourceNode = nodes.find(n => n.id === edge.source_node_id);
              const targetNode = nodes.find(n => n.id === edge.target_node_id);

              if (!sourceNode || !targetNode) return null;

              const edgeType = edgeTypes.find(et => et.type === edge.edge_type);
              const color = edgeType ? edgeType.color : '#666';

              return (
                <g key={edge.id}>
                  <line
                    x1={sourceNode.position.x + 50}
                    y1={sourceNode.position.y + 25}
                    x2={targetNode.position.x + 50}
                    y2={targetNode.position.y + 25}
                    stroke={color}
                    strokeWidth="2"
                    markerEnd="url(#arrowhead)"
                    className={selectedEdge === edge.id ? 'selected-edge' : ''}
                    onClick={() => handleEdgeClick(edge.id)}
                  />
                  <text
                    x={(sourceNode.position.x + targetNode.position.x) / 2 + 50}
                    y={(sourceNode.position.y + targetNode.position.y) / 2 + 15}
                    textAnchor="middle"
                    fontSize="10"
                    fill={color}
                  >
                    {edge.edge_type}
                  </text>
                </g>
              );
            })}

            {/* Arrow marker definition */}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#666" />
              </marker>
            </defs>
          </svg>

          {/* Render nodes */}
          {nodes.map(node => {
            const nodeType = nodeTypes.find(nt => nt.type === node.node_type);
            const color = nodeType ? nodeType.color : '#666';

            return (
              <div
                key={node.id}
                className={`node ${selectedNode === node.id ? 'selected' : ''}`}
                style={{
                  left: node.position.x,
                  top: node.position.y,
                  borderColor: color,
                }}
                draggable
                onDragStart={e => handleNodeDragStart(e, node.id)}
                onClick={() => handleNodeClick(node.id)}
                onDoubleClick={() => handleNodeDoubleClick(node.id)}
              >
                <div className="node-header">
                  <span className="node-icon">{nodeType?.icon || '📦'}</span>
                  <span className="node-name">{node.name}</span>
                </div>
                <div className="node-type-label">
                  {nodeType?.label || node.node_type}
                </div>
              </div>
            );
          })}
        </div>

        <div className="right-panel">
          {selectedNode && (
            <div className="node-properties">
              <h3>Node Properties</h3>
              <p>
                <strong>ID:</strong> {selectedNode}
              </p>
              <p>
                <strong>Name:</strong>{' '}
                {nodes.find(n => n.id === selectedNode)?.name}
              </p>
              <p>
                <strong>Type:</strong>{' '}
                {nodes.find(n => n.id === selectedNode)?.node_type}
              </p>
              <button onClick={deleteSelectedNode} className="btn btn-danger">
                🗑️ Delete Node
              </button>
            </div>
          )}

          {selectedEdge && (
            <div className="edge-properties">
              <h3>Edge Properties</h3>
              <p>
                <strong>ID:</strong> {selectedEdge}
              </p>
              <p>
                <strong>Type:</strong>{' '}
                {edges.find(e => e.id === selectedEdge)?.edge_type}
              </p>
              <button onClick={deleteSelectedEdge} className="btn btn-danger">
                🗑️ Delete Edge
              </button>
            </div>
          )}

          {naturalLanguage && (
            <div className="natural-language">
              <h3>🤖 Natural Language Translation</h3>
              <p>{naturalLanguage}</p>
            </div>
          )}

          {insights.length > 0 && (
            <div className="insights">
              <h3>💡 AI Insights</h3>
              {insights.map((insight, index) => (
                <div key={index} className="insight">
                  <p>
                    <strong>{insight.insight_type}:</strong>{' '}
                    {insight.description}
                  </p>
                  <p>
                    <strong>Confidence:</strong> {insight.confidence_score}
                  </p>
                  {insight.recommendations.length > 0 && (
                    <div>
                      <strong>Recommendations:</strong>
                      <ul>
                        {insight.recommendations.map((rec, i) => (
                          <li key={i}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Node Panel */}
      {showNodePanel && (
        <div className="modal-overlay" onClick={() => setShowNodePanel(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Add Node</h3>
            <div className="node-options">
              {nodeTypes.map(nodeType => (
                <div
                  key={nodeType.type}
                  className="node-option"
                  onClick={() => addNode(nodeType.type, 100, 100)}
                >
                  <span className="node-icon">{nodeType.icon}</span>
                  <span className="node-label">{nodeType.label}</span>
                </div>
              ))}
            </div>
            <button
              onClick={() => setShowNodePanel(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Export Panel */}
      {showExportPanel && (
        <div
          className="modal-overlay"
          onClick={() => setShowExportPanel(false)}
        >
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Export Query</h3>
            <div className="export-options">
              <label>Format:</label>
              <select
                value={exportFormat}
                onChange={e => setExportFormat(e.target.value)}
              >
                {exportFormats.map(format => (
                  <option key={format.value} value={format.value}>
                    {format.icon} {format.label}
                  </option>
                ))}
              </select>
              <button onClick={exportQuery} className="btn btn-primary">
                Export
              </button>
            </div>

            {exportContent && (
              <div className="export-content">
                <h4>Exported Content:</h4>
                <pre>{exportContent}</pre>
                <button
                  onClick={() => navigator.clipboard.writeText(exportContent)}
                  className="btn btn-secondary"
                >
                  📋 Copy to Clipboard
                </button>
              </div>
            )}

            <button
              onClick={() => setShowExportPanel(false)}
              className="btn btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default VisualQueryBuilder;
