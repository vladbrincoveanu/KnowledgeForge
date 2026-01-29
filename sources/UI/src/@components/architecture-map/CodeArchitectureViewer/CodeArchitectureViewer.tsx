import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  Position,
  useReactFlow,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import './CodeArchitectureViewer.scss';
import { codeArchitectureAPI } from '../../../services/api';
import CustomNode from './CustomNode';

interface CodeEntity {
  id: string;
  name: string;
  entity_type: string;
  language?: string;
  file_path?: string;
  line_start?: number;
  attributes?: {
    is_external?: boolean;
    decorators?: string[];
    [key: string]: any;
  };
  level?: string;
}

interface CodeRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string | null;
  target_entity_name?: string;
  relationship_type: string;
  context?: string;
  line_number?: number;
  attributes?: Record<string, any>;
}

interface C4Level {
  entities: CodeEntity[];
  relationships: CodeRelationship[];
}

interface C4Architecture {
  c4_model_version: string;
  system_context: any;
  containers?: any[];  // Array format from backend
  components?: any[];  // Array format from backend
  context_level?: C4Level;
  container_level?: C4Level;  // Transformed format
  component_level?: C4Level;  // Transformed format
  code_level?: C4Level;
}

const nodeTypes = {
  custom: CustomNode,
};

// Layout function using dagre with hierarchical structure
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  // Configure layout for LEFT-TO-RIGHT flow with better spacing
  dagreGraph.setGraph({ 
    rankdir: direction,      // LR = Left to Right for clearer hierarchy
    align: 'UL',
    ranksep: 250,            // Large spacing between hierarchy levels
    nodesep: 80,             // Vertical spacing between nodes at same level
    edgesep: 20,
    marginx: 50,
    marginy: 50,
    ranker: 'network-simplex', // Better for hierarchical layouts
  });

  // Add nodes to graph
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { 
      width: 220, 
      height: 100,
    });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 110,
        y: nodeWithPosition.y - 50,
      },
      sourcePosition: Position.Right,  // Changed for LR layout
      targetPosition: Position.Left,   // Changed for LR layout
    };
  });

  return { nodes: layoutedNodes, edges };
};

const CodeArchitectureViewer: React.FC = () => {
  return (
    <ReactFlowProvider>
      <CodeArchitectureViewerInner />
    </ReactFlowProvider>
  );
};

const CodeArchitectureViewerInner: React.FC = () => {
  const [architecture, setArchitecture] = useState<C4Architecture | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();
  
  // Filters - default to showing container and code levels for better hierarchy
  const [selectedLevels, setSelectedLevels] = useState<string[]>(['container_level', 'code_level']);
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<string[]>([]);
  const [selectedRelationshipTypes, setSelectedRelationshipTypes] = useState<string[]>([]);
  const [showExternal, setShowExternal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  
  const [entityTypes, setEntityTypes] = useState<string[]>([]);
  const [relationshipTypes, setRelationshipTypes] = useState<string[]>([]);

  // Load architecture data
  useEffect(() => {
    const loadArchitecture = async () => {
      try {
        setLoading(true);
        const data = await codeArchitectureAPI.getArchitecture();
        
        // Transform containers array into container_level structure
        if (data.containers && Array.isArray(data.containers)) {
          const containerEntities: CodeEntity[] = data.containers.map((container: any, idx: number) => ({
            id: `container_${container.name || idx}`,
            name: container.name,
            entity_type: 'container',
            language: container.technology || 'Unknown',
            file_path: container.path,
            attributes: {
              container_type: container.container_type,
              protocol: container.protocol,
              runtime_info: container.runtime_info,
            },
          }));
          
          // Create relationships from containers to their code entities
          const containerRelationships: CodeRelationship[] = [];
          if (data.code_level?.entities) {
            containerEntities.forEach(container => {
              const containerPath = container.file_path || '';
              // Find code entities that belong to this container
              data.code_level.entities
                .filter((entity: CodeEntity) => {
                  const entityPath = entity.file_path || '';
                  return entityPath.startsWith(containerPath);
                })
                .forEach((entity: CodeEntity) => {
                  containerRelationships.push({
                    id: `rel_${container.id}_${entity.id}`,
                    source_entity_id: container.id,
                    target_entity_id: entity.id,
                    relationship_type: 'contains',
                    attributes: {},
                  });
                });
            });
          }
          
          data.container_level = {
            entities: containerEntities,
            relationships: containerRelationships,
          };
        }
        
        // Transform components array into component_level structure
        if (data.components && Array.isArray(data.components)) {
          const componentEntities: CodeEntity[] = [];
          
          data.components.forEach((component: any, groupIdx: number) => {
            // Check if this is a component group
            if (component.type === 'component_group' && component.components && Array.isArray(component.components)) {
              // Expand the grouped components
              component.components.forEach((compName: string, idx: number) => {
                componentEntities.push({
                  id: `component_${groupIdx}_${idx}`,
                  name: compName,
                  entity_type: 'component',
                  language: 'Unknown',
                  file_path: component.name, // Use group name as path/module
                  attributes: {
                    component_type: component.component_type || 'Component',
                    group: component.name,
                  },
                });
              });
            } else {
              // Single component (not grouped)
              componentEntities.push({
                id: `component_${groupIdx}`,
                name: component.name || `Component ${groupIdx}`,
                entity_type: 'component',
                language: component.technology || 'Unknown',
                file_path: component.path || component.file,
                attributes: component.attributes || {},
              });
            }
          });
          
          data.component_level = {
            entities: componentEntities,
            relationships: [],
          };
        }
        
        setArchitecture(data);
        
        // Extract unique entity and relationship types
        const allEntities: CodeEntity[] = [];
        const allRelationships: CodeRelationship[] = [];
        
        ['context_level', 'container_level', 'component_level', 'code_level'].forEach(level => {
          if (data[level as keyof C4Architecture]) {
            const levelData = data[level as keyof C4Architecture] as C4Level;
            if (levelData.entities) allEntities.push(...levelData.entities);
            if (levelData.relationships) allRelationships.push(...levelData.relationships);
          }
        });
        
        const uniqueEntityTypes = Array.from(new Set(allEntities.map(e => e.entity_type)));
        const uniqueRelTypes = Array.from(new Set(allRelationships.map(r => r.relationship_type)));
        
        setEntityTypes(uniqueEntityTypes.sort());
        setRelationshipTypes(uniqueRelTypes.sort());
        setSelectedEntityTypes(uniqueEntityTypes);
        setSelectedRelationshipTypes(uniqueRelTypes);
        
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load architecture');
      } finally {
        setLoading(false);
      }
    };
    
    loadArchitecture();
  }, []);

  // Process architecture data into graph format
  useEffect(() => {
    if (!architecture) return;

    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];

    // Collect entities and relationships from selected levels
    selectedLevels.forEach(level => {
      if (architecture[level as keyof C4Architecture]) {
        const levelData = architecture[level as keyof C4Architecture] as C4Level;
        if (levelData.entities) {
          // Add level metadata to each entity
          allEntities.push(...levelData.entities.map(e => ({ ...e, level })));
        }
        if (levelData.relationships) {
          allRelationships.push(...levelData.relationships);
        }
      }
    });

    // Filter entities
    let filteredEntities = allEntities.filter(e => {
      const typeMatch = selectedEntityTypes.length === 0 || selectedEntityTypes.includes(e.entity_type);
      const externalMatch = showExternal || !e.attributes?.is_external;
      const searchMatch = searchTerm === '' || 
        e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        e.file_path?.toLowerCase().includes(searchTerm.toLowerCase());
      
      return typeMatch && externalMatch && searchMatch;
    });

    // Create entity lookup
    const entityIds = new Set(filteredEntities.map(e => e.id));

    // Filter relationships
    const filteredRelationships = allRelationships.filter(r => {
      const typeMatch = selectedRelationshipTypes.length === 0 || selectedRelationshipTypes.includes(r.relationship_type);
      const validSource = entityIds.has(r.source_entity_id);
      const validTarget = r.target_entity_id && entityIds.has(r.target_entity_id);
      
      return typeMatch && validSource && validTarget;
    });

    // Convert to React Flow format
    const rfNodes: Node[] = filteredEntities.map(e => {
      // Shorten the label - take last part of dotted name and remove common suffixes
      let shortName = e.name.includes('.') 
        ? e.name.split('.').pop() || e.name
        : e.name;
      
      // Remove redundant type suffixes (e.g., "SlurmJobSpec.Class" -> "SlurmJobSpec")
      const typeSuffixes = ['Class', 'Function', 'Method', 'Module', 'File', 'Variable', 'Constant'];
      typeSuffixes.forEach(suffix => {
        if (shortName.endsWith(suffix) && shortName !== suffix) {
          shortName = shortName.slice(0, -suffix.length);
        }
      });
      
      // Clean up any trailing underscores or dots
      shortName = shortName.replace(/[._]+$/, '');
      
      // Get display type
      const displayType = e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);
      
      return {
        id: e.id,
        type: 'custom',
        position: { x: 0, y: 0 }, // Will be set by layout
        data: {
          label: shortName,
          fullName: e.name,
          type: e.entity_type,
          displayType: displayType,
          file: e.file_path,
          line: e.line_start || undefined,
          isExternal: e.attributes?.is_external,
          decorators: e.attributes?.decorators,
          level: e.level,  // Store level for layout grouping
        },
      };
    });

    const rfEdges: Edge[] = filteredRelationships
      .filter(r => r.target_entity_id)
      .map((r, idx) => ({
        id: `edge-${idx}`,
        source: r.source_entity_id,
        target: r.target_entity_id!,
        type: 'smoothstep',
        animated: false,
        style: { 
          stroke: '#b0bec5', 
          strokeWidth: 2,
        },
        // Remove labels for cleaner look
        // label: r.relationship_type,
      }));

    // Apply layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(rfNodes, rfEdges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
    
    // Fit view after layout to show entire graph
    window.requestAnimationFrame(() => {
      setTimeout(() => {
        fitView({ 
          padding: 0.1,
          includeHiddenNodes: false,
          duration: 500,
          maxZoom: 0.9,
          minZoom: 0.05,
        });
      }, 100);
    });
  }, [architecture, selectedLevels, selectedEntityTypes, selectedRelationshipTypes, showExternal, searchTerm, fitView]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data);
  }, []);

  const avgConnections = nodes.length > 0 
    ? (edges.length / nodes.length).toFixed(1)
    : '0';

  const toggleLevel = (level: string) => {
    setSelectedLevels(prev =>
      prev.includes(level)
        ? prev.filter(l => l !== level)
        : [...prev, level]
    );
  };

  const toggleEntityType = (type: string) => {
    setSelectedEntityTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  const toggleRelationshipType = (type: string) => {
    setSelectedRelationshipTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  if (loading) {
    return (
      <div className="code-architecture-viewer">
        <div className="loading">Loading architecture...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="code-architecture-viewer">
        <div className="error">
          <h3>Error loading architecture</h3>
          <p>{error}</p>
          <p className="hint">Make sure you've run the extraction: <code>python -m services.code_extraction.c4_extractor</code></p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-architecture-viewer">
      <div className="viewer-header">
        <h2>🏗️ Code Architecture Map</h2>
        <p>Hierarchical visualization from high-level modules to detailed code dependencies</p>
      </div>

      <div className="viewer-layout">
        <aside className="filters-sidebar">
          <div className="filter-section">
            <h3>Statistics</h3>
            <div className="stats">
              <div className="stat">
                <span className="stat-value">{nodes.length}</span>
                <span className="stat-label">Entities</span>
              </div>
              <div className="stat">
                <span className="stat-value">{edges.length}</span>
                <span className="stat-label">Relationships</span>
              </div>
              <div className="stat">
                <span className="stat-value">{avgConnections}</span>
                <span className="stat-label">Avg Connections</span>
              </div>
            </div>
          </div>

          <div className="filter-section">
            <h3>Search</h3>
            <input
              type="text"
              placeholder="Search entities..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="filter-section">
            <h3>C4 Levels</h3>
            {['context_level', 'container_level', 'component_level', 'code_level'].map(level => (
              <label key={level} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={selectedLevels.includes(level)}
                  onChange={() => toggleLevel(level)}
                />
                <span>{level.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
              </label>
            ))}
          </div>

          <div className="filter-section">
            <h3>Entity Types</h3>
            <div className="entity-legend">
              <div className="legend-item">
                <div className="shape-indicator shape-rounded-rect" style={{backgroundColor: '#e3f2fd', borderColor: '#1976d2'}}></div>
                <span>Class</span>
              </div>
              <div className="legend-item">
                <div className="shape-indicator shape-rounded-rect" style={{backgroundColor: '#fff3e0', borderColor: '#f57c00'}}></div>
                <span>Function</span>
              </div>
              <div className="legend-item">
                <div className="shape-indicator shape-rect" style={{backgroundColor: '#f3e5f5', borderColor: '#7b1fa2'}}></div>
                <span>Module</span>
              </div>
              <div className="legend-item">
                <div className="shape-indicator shape-circle" style={{backgroundColor: '#e8f5e9', borderColor: '#388e3c'}}></div>
                <span>Variable</span>
              </div>
            </div>
            <div className="checkbox-group">
              {entityTypes.map(type => (
                <label key={type} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedEntityTypes.includes(type)}
                    onChange={() => toggleEntityType(type)}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <h3>Relationship Types</h3>
            <div className="checkbox-group">
              {relationshipTypes.map(type => (
                <label key={type} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedRelationshipTypes.includes(type)}
                    onChange={() => toggleRelationshipType(type)}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={showExternal}
                onChange={e => setShowExternal(e.target.checked)}
              />
              <span>Show External Dependencies</span>
            </label>
          </div>
        </aside>

        <main className="graph-container">
          {nodes.length === 0 ? (
            <div className="empty-state">
              <p>No entities match the current filters</p>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              nodeTypes={nodeTypes}
              fitView
              attributionPosition="bottom-left"
              defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
              minZoom={0.05}
              maxZoom={1.5}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e0e0e0" />
              <Controls />
            </ReactFlow>
          )}
        </main>

        {selectedNode && (
          <aside className="node-details-panel">
            <div className="panel-header">
              <h3>Node Details</h3>
              <button className="close-btn" onClick={() => setSelectedNode(null)}>×</button>
            </div>
            <div className="panel-content">
              <div className="detail-row">
                <span className="detail-label">Type:</span>
                <span className="detail-value">{selectedNode.type}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Name:</span>
                <span className="detail-value">{selectedNode.fullName || selectedNode.label}</span>
              </div>
              {selectedNode.file && (
                <div className="detail-row">
                  <span className="detail-label">File:</span>
                  <span className="detail-value file-path">{selectedNode.file}</span>
                </div>
              )}
              {selectedNode.line && (
                <div className="detail-row">
                  <span className="detail-label">Line:</span>
                  <span className="detail-value">{selectedNode.line}</span>
                </div>
              )}
              {selectedNode.decorators && selectedNode.decorators.length > 0 && (
                <div className="detail-row">
                  <span className="detail-label">Decorators:</span>
                  <div className="decorator-list">
                    {selectedNode.decorators.map((dec: string, idx: number) => (
                      <span key={idx} className="decorator-badge">{dec}</span>
                    ))}
                  </div>
                </div>
              )}
              {selectedNode.isExternal && (
                <div className="detail-row">
                  <span className="external-badge">🌐 External Dependency</span>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
};

export default CodeArchitectureViewer;
