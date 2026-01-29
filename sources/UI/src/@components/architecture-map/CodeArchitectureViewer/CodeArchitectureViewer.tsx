import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  MarkerType,
  Position,
  useReactFlow,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import './CodeArchitectureViewer.scss';
import { codeArchitectureAPI } from '../../../services/api';
import CustomNode from './CustomNode';
import ContainerNode from './ContainerNode';
import C4Edge from './C4Edge';

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

interface C4DiagramRelationship {
  source: string;
  destination: string;
  description?: string;
  relationship_type?: string;
}

interface C4Relationships {
  context?: C4DiagramRelationship[];
  containers?: C4DiagramRelationship[];
}

interface C4Architecture {
  c4_model_version: string;
  system_context: any;
  containers?: any[];  // Array format from backend
  components?: any[];  // Array format from backend
  relationships?: C4Relationships;
  metadata?: {
    runtime?: {
      platform?: string;
      cluster?: any;
    };
  };
  context_level?: C4Level;
  container_level?: C4Level;  // Transformed format
  component_level?: C4Level;  // Transformed format
  code_level?: C4Level;
}

const edgeTypes = {
  C4Edge,
};

const buildContainerId = (container: any, idx: number) => `container_${container.name || idx}`;

const generateC4Edges = (containers: any[] = []): Edge[] => {
  const nameToId = new Map<string, string>();

  containers.forEach((container, idx) => {
    if (container?.name) {
      nameToId.set(container.name, buildContainerId(container, idx));
    }
  });

  const edges: Edge[] = [];

  containers.forEach((container, idx) => {
    const sourceId = buildContainerId(container, idx);
    const protocol = typeof container?.protocol === 'string' ? container.protocol.trim() : '';
    const label = protocol ? protocol.toUpperCase() : undefined;
    const dependencies = Array.isArray(container?.dependencies_internal)
      ? container.dependencies_internal
      : [];

    dependencies.forEach((dependencyName, depIdx) => {
      const targetId = nameToId.get(String(dependencyName));
      if (!targetId) {
        return;
      }

      edges.push({
        id: `c4-edge-${sourceId}-${targetId}-${depIdx}`,
        source: sourceId,
        target: targetId,
        label,
        type: 'C4Edge',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      });
    });
  });

  return edges;
};

const nodeTypes = {
  custom: CustomNode,
  container: ContainerNode,
};

// Layout function - grid layout for components in containers
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  // Separate parent containers and child nodes
  const containerNodes = nodes.filter(n => n.type === 'container');
  const childNodes = nodes.filter(n => n.parentNode);
  const standaloneNodes = nodes.filter(n => !n.type?.includes('container') && !n.parentNode);
  
  // Layout child nodes within their parent containers
  if (containerNodes.length > 0) {
    // Position containers
    const containerSpacing = 60;
    let currentX = 100;

    const childNodeWidth = 220;
    const childNodeHeight = 100;
    const childSpacing = 30;
    const childStartX = 40;
    const childStartY = 80;

    containerNodes.forEach(container => {
      container.position = { x: currentX, y: 100 };

      // Get children of this container
      const children = childNodes.filter(n => n.parentNode === container.id);

      // Layout children in a grid inside the container (more horizontal when possible)
      const minColumns = 2;
      const maxColumns = 4;
      const childrenPerRow = Math.min(
        maxColumns,
        Math.max(minColumns, Math.ceil(children.length / 2))
      );

      children.forEach((child, idx) => {
        const row = Math.floor(idx / childrenPerRow);
        const col = idx % childrenPerRow;

        child.position = {
          x: childStartX + (col * (childNodeWidth + childSpacing)),
          y: childStartY + (row * (childNodeHeight + childSpacing)),
        };
        child.sourcePosition = Position.Right;
        child.targetPosition = Position.Left;
      });

      if (children.length > 0) {
        const rows = Math.ceil(children.length / childrenPerRow);
        const contentWidth = (childStartX * 2) + (childrenPerRow * childNodeWidth) + ((childrenPerRow - 1) * childSpacing);
        const contentHeight = childStartY + (rows * childNodeHeight) + ((rows - 1) * childSpacing) + 50;

        container.style = {
          ...container.style,
          width: Math.max(640, contentWidth),
          height: Math.max(420, contentHeight),
        };
      }

      currentX += (container.style?.width as number || 700) + containerSpacing;
    });

    return { 
      nodes: [...containerNodes, ...childNodes, ...standaloneNodes], 
      edges 
    };
  }
  
  // Check if we have components without relationships (independent endpoints)
  const hasRelationships = edges.length > 0;
  
  if (!hasRelationships && nodes.length > 0) {
    // Grid layout for independent components
    const methodGroups = new Map<string, Node[]>();
    nodes.forEach(node => {
      const method = node.data.type === 'component' 
        ? (node.data.fullName?.split(' ')[0] || 'OTHER')
        : 'OTHER';
      
      if (!methodGroups.has(method)) {
        methodGroups.set(method, []);
      }
      methodGroups.get(method)!.push(node);
    });
    
    // Layout in columns by method
    const methodOrder = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OTHER'];
    let columnX = 100;
    const columnWidth = 280;
    const rowHeight = 150;
    
    const layoutedNodes = nodes.map((node) => {
      const method = node.data.type === 'component' 
        ? (node.data.fullName?.split(' ')[0] || 'OTHER')
        : 'OTHER';
      
      const methodIndex = methodOrder.indexOf(method);
      const groupNodes = methodGroups.get(method) || [];
      const nodeIndex = groupNodes.indexOf(node);
      
      return {
        ...node,
        position: {
          x: columnX + (methodIndex * columnWidth),
          y: 100 + (nodeIndex * rowHeight),
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    });
    
    return { nodes: layoutedNodes, edges };
  }
  
  // Hierarchical layout with dagre for connected graphs
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  dagreGraph.setGraph({ 
    rankdir: direction,
    align: 'UL',
    ranksep: 250,
    nodesep: 80,
    edgesep: 20,
    marginx: 50,
    marginy: 50,
    ranker: 'network-simplex',
  });

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
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
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
  
  // Filters - default to showing only component level (components auto-connect)
  const [selectedLevel, setSelectedLevel] = useState<string>('component_level');
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<string[]>([]);
  const [selectedRelationshipTypes, setSelectedRelationshipTypes] = useState<string[]>([]);
  const [showExternal, setShowExternal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  
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
              runtime_environment: container.runtime_environment,
              deployment: container.deployment,
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

          // Merge container-level relationships from C4 JSON
          if (data.relationships?.containers?.length) {
            const containerIdByName = new Map(
              containerEntities.map(c => [c.name, c.id])
            );

            data.relationships.containers.forEach((rel: C4DiagramRelationship, idx: number) => {
              const sourceId = containerIdByName.get(rel.source);
              const targetId = containerIdByName.get(rel.destination);

              if (sourceId && targetId) {
                containerRelationships.push({
                  id: `rel_container_${idx}`,
                  source_entity_id: sourceId,
                  target_entity_id: targetId,
                  relationship_type: rel.relationship_type || 'depends_on',
                  attributes: { description: rel.description },
                });
              }
            });
          }
          
          data.container_level = {
            entities: containerEntities,
            relationships: containerRelationships,
          };
        }

        // Transform context data into context_level structure
        if (data.system_context && !data.context_level) {
          const contextEntities: CodeEntity[] = [];
          const contextRelationships: CodeRelationship[] = [];

          const systemName = data.system_context?.name || 'System';
          const systemId = `context_system_${systemName}`;

          contextEntities.push({
            id: systemId,
            name: systemName,
            entity_type: 'system',
            language: 'Unknown',
            file_path: '',
            attributes: {
              owner_team: data.system_context?.owner_team,
              business_domain: data.system_context?.business_domain,
              criticality: data.system_context?.criticality,
              purpose: data.system_context?.purpose,
            },
          });

          const actorEntities = (data.system_context?.actors || []).map((actor: any, idx: number) => ({
            id: `context_actor_${idx}`,
            name: actor.name || `Actor ${idx + 1}`,
            entity_type: actor.type || 'person',
            language: 'Unknown',
            file_path: '',
            attributes: {},
          }));

          const externalEntities = (data.system_context?.external_dependencies || []).map((dep: any, idx: number) => ({
            id: `context_external_${idx}`,
            name: dep.name || dep.url || `External ${idx + 1}`,
            entity_type: dep.type || 'external_system',
            language: 'Unknown',
            file_path: dep.detected_from || '',
            attributes: {
              url: dep.url,
              detected_from: dep.detected_from,
            },
          }));

          contextEntities.push(...actorEntities, ...externalEntities);

          const contextIdByName = new Map(
            contextEntities.map(entity => [entity.name, entity.id])
          );

          if (data.relationships?.context?.length) {
            data.relationships.context.forEach((rel: C4DiagramRelationship, idx: number) => {
              const sourceId = contextIdByName.get(rel.source);
              const targetId = contextIdByName.get(rel.destination);

              if (sourceId && targetId) {
                contextRelationships.push({
                  id: `rel_context_${idx}`,
                  source_entity_id: sourceId,
                  target_entity_id: targetId,
                  relationship_type: rel.relationship_type || 'uses',
                  attributes: { description: rel.description },
                });
              }
            });
          }

          data.context_level = {
            entities: contextEntities,
            relationships: contextRelationships,
          };
        }
        
        // Transform components array into component_level structure
        if (data.components && Array.isArray(data.components)) {
          const componentEntities: CodeEntity[] = [];
          const componentRelationships: CodeRelationship[] = [];
          
          data.components.forEach((component: any, groupIdx: number) => {
            // Check if this is a component group
            if (component.type === 'component_group' && component.components && Array.isArray(component.components)) {
              // Expand the grouped components
              component.components.forEach((compName: string, idx: number) => {
                const compId = `component_${groupIdx}_${idx}`;
                componentEntities.push({
                  id: compId,
                  name: compName,
                  entity_type: 'component',
                  language: 'Unknown',
                  file_path: component.name, // Use group name as path/module
                  attributes: {
                    component_type: component.component_type || 'Component',
                    group: component.name,
                    container: component.container,
                  },
                });
                
                // Create relationship to container
                if (component.container && data.container_level?.entities) {
                  const containerEntity = data.container_level.entities.find(
                    (c: CodeEntity) => c.name === component.container
                  );
                  if (containerEntity) {
                    componentRelationships.push({
                      id: `rel_comp_${compId}_${containerEntity.id}`,
                      source_entity_id: containerEntity.id,
                      target_entity_id: compId,
                      relationship_type: 'contains',
                      attributes: {},
                    });
                  }
                }
              });
            } else {
              // Single component (not grouped)
              const compId = `component_${groupIdx}`;
              componentEntities.push({
                id: compId,
                name: component.name || `Component ${groupIdx}`,
                entity_type: 'component',
                language: component.technology || 'Unknown',
                file_path: component.path || component.file,
                attributes: {
                  ...component.attributes,
                  component_type: component.component_type,
                  container: component.container,
                  endpoint_path: component.endpoint_path,
                  endpoint_method: component.endpoint_method,
                },
              });
              
              // Create relationship to container
              if (component.container && data.container_level?.entities) {
                const containerEntity = data.container_level.entities.find(
                  (c: CodeEntity) => c.name === component.container
                );
                if (containerEntity) {
                  componentRelationships.push({
                    id: `rel_comp_${compId}_${containerEntity.id}`,
                    source_entity_id: containerEntity.id,
                    target_entity_id: compId,
                    relationship_type: 'contains',
                    attributes: {},
                  });
                }
              }
            }
          });
          
          // Components don't need relationships - they're independent endpoints
          // No inter-component relationships needed
          
          data.component_level = {
            entities: componentEntities,
            relationships: componentRelationships,
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

    // Collect entities and relationships from the selected level
    if (architecture[selectedLevel as keyof C4Architecture]) {
      const levelData = architecture[selectedLevel as keyof C4Architecture] as C4Level;
      if (levelData.entities) {
        // Add level metadata to each entity
        allEntities.push(...levelData.entities.map(e => ({ ...e, level: selectedLevel })));
      }
      if (levelData.relationships) {
        allRelationships.push(...levelData.relationships);
      }
    }

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
    const rfNodes: Node[] = [];
    
    // If we're showing components, create container frames based on their actual container assignment
    if (selectedLevel === 'component_level' && filteredEntities.some(e => e.entity_type === 'component')) {
      const componentEntities = filteredEntities.filter(e => e.entity_type === 'component');
      
      // Group components by their actual container attribute
      const containerGroups = new Map<string, typeof componentEntities>();
      componentEntities.forEach(comp => {
        const containerName = (comp.attributes?.container as string) || 'Unknown';
        
        if (!containerGroups.has(containerName)) {
          containerGroups.set(containerName, []);
        }
        containerGroups.get(containerName)!.push(comp);
      });
      
      // Create container frames for each group
      let currentX = 100;
      containerGroups.forEach((components, containerName) => {
        // Find the actual container info from architecture data
        const containerInfo = architecture?.containers?.find((c: any) => c.name === containerName);
        const displayName = containerInfo?.name || containerName;
        const containerType = containerInfo?.container_type || 'Service';
        const technology = containerInfo?.technology || 'Unknown';
        
        // Create container parent node
        const containerNode: Node = {
          id: `container_frame_${containerName}`,
          type: 'container',
          position: { x: currentX, y: 100 },
          data: {
            label: displayName,
            containerType: containerType,
            technology: technology,
          },
          style: {
            width: 700,
            height: Math.max(500, Math.ceil(components.length / 2) * 150 + 150),
            backgroundColor: 'rgba(99, 102, 241, 0.05)',
            border: '2px solid #6366f1',
            borderRadius: '12px',
            padding: '20px',
          },
        };
        rfNodes.push(containerNode);
        
        // Add component nodes as children
        components.forEach((e, idx) => {
          let shortName = e.name.includes('.') 
            ? e.name.split('.').pop() || e.name
            : e.name;
          
          const typeSuffixes = ['Class', 'Function', 'Method', 'Module', 'File', 'Variable', 'Constant'];
          typeSuffixes.forEach(suffix => {
            if (shortName.endsWith(suffix) && shortName !== suffix) {
              shortName = shortName.slice(0, -suffix.length);
            }
          });
          
          shortName = shortName.replace(/[._]+$/, '');
          const displayType = e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);
          
          // Layout children in a 2-column grid
          const childrenPerRow = 2;
          const childSpacing = 30;
          const childStartX = 40;
          const childStartY = 80;
          const row = Math.floor(idx / childrenPerRow);
          const col = idx % childrenPerRow;
          
          const node: Node = {
            id: e.id,
            type: 'custom',
            position: {
              x: childStartX + (col * (220 + childSpacing)),
              y: childStartY + (row * (120 + childSpacing)),
            },
            parentNode: containerNode.id,
            extent: 'parent',
            data: {
              label: shortName,
              fullName: e.name,
              type: e.entity_type,
              displayType: displayType,
              file: e.file_path,
              line: e.line_start || undefined,
              isExternal: e.attributes?.is_external,
              decorators: e.attributes?.decorators,
              level: e.level,
            },
          };
          rfNodes.push(node);
        });
        
        currentX += 750; // Space between containers
      });
      
      // Add any non-component entities
      const nonComponents = filteredEntities.filter(e => e.entity_type !== 'component');
      nonComponents.forEach(e => {
        let shortName = e.name.includes('.') 
          ? e.name.split('.').pop() || e.name
          : e.name;
        
        const typeSuffixes = ['Class', 'Function', 'Method', 'Module', 'File', 'Variable', 'Constant'];
        typeSuffixes.forEach(suffix => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });
        
        shortName = shortName.replace(/[._]+$/, '');
        const displayType = e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);
        
        rfNodes.push({
          id: e.id,
          type: 'custom',
          position: { x: 0, y: 0 },
          data: {
            label: shortName,
            fullName: e.name,
            type: e.entity_type,
            displayType: displayType,
            file: e.file_path,
            line: e.line_start || undefined,
            isExternal: e.attributes?.is_external,
            decorators: e.attributes?.decorators,
            level: e.level,
          },
        });
      });
    } else {
      // Container-level framing for Kubernetes
      const hasContainerLevel = selectedLevel === 'container_level';
      const containerEntities = filteredEntities.filter(e => e.entity_type === 'container');
      const containerInfoByName = new Map(
        (architecture?.containers || []).map((container: any) => [container.name, container])
      );

      const isKubernetesEntity = (entity: CodeEntity) => {
        const tech = String(entity.language || '').toLowerCase();
        const containerType = String(entity.attributes?.container_type || '').toLowerCase();
        const runtimeEnv = String(entity.attributes?.runtime_environment || '').toLowerCase();
        const deployment = String(entity.attributes?.deployment || '').toLowerCase();

        return tech.includes('kubernetes') ||
          containerType.includes('helm') ||
          containerType.includes('kubernetes') ||
          runtimeEnv.includes('kubernetes') ||
          deployment.includes('helm') ||
          deployment.includes('kustomize') ||
          deployment.includes('manifest');
      };

      let clusterNodeId: string | null = null;

      if (hasContainerLevel && containerEntities.length > 0) {
        const kubernetesContainers = containerEntities.filter(isKubernetesEntity);

        if (kubernetesContainers.length > 0) {
          const columns = Math.min(4, Math.max(2, Math.ceil(kubernetesContainers.length / 2)));
          const rows = Math.ceil(kubernetesContainers.length / columns);
          const clusterWidth = Math.max(720, (columns * 240) + 200);
          const clusterHeight = Math.max(420, (rows * 140) + 180);
          const clusterMeta = architecture?.metadata?.runtime?.cluster;
          clusterNodeId = 'cluster_kubernetes';
          rfNodes.push({
            id: clusterNodeId,
            type: 'container',
            position: { x: 80, y: 80 },
            className: 'cluster-frame',
            data: {
              label: 'Kubernetes Cluster',
              containerType: 'Runtime Environment',
              technology: 'Kubernetes',
              clusterMeta,
            },
            style: {
              width: clusterWidth,
              height: clusterHeight,
              backgroundColor: 'rgba(148, 163, 184, 0.08)',
              border: '2px dashed #cbd5e1',
              borderRadius: '16px',
              padding: '20px',
            },
          });
        }
      }

      // Original logic for non-component entities
      filteredEntities.forEach(e => {
        let shortName = e.name.includes('.') 
          ? e.name.split('.').pop() || e.name
          : e.name;
        
        const typeSuffixes = ['Class', 'Function', 'Method', 'Module', 'File', 'Variable', 'Constant'];
        typeSuffixes.forEach(suffix => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });
        
        shortName = shortName.replace(/[._]+$/, '');
        const displayType = e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);
        
        const containerInfo = e.entity_type === 'container'
          ? containerInfoByName.get(e.name)
          : null;

        const node: Node = {
          id: e.id,
          type: 'custom',
          position: { x: 0, y: 0 },
          data: {
            label: shortName,
            fullName: e.name,
            type: e.entity_type,
            displayType: displayType,
            file: e.file_path,
            line: e.line_start || undefined,
            isExternal: e.attributes?.is_external,
            decorators: e.attributes?.decorators,
            level: e.level,
            containerMeta: containerInfo ? {
              container_type: containerInfo.container_type,
              technology: containerInfo.technology,
              protocol: containerInfo.protocol,
              runtime_environment: containerInfo.runtime_environment,
              deployment: containerInfo.deployment,
              description: containerInfo.description,
              health_endpoint: containerInfo.health_endpoint,
              repository_url: containerInfo.repository_url,
            } : undefined,
          },
        };

        if (clusterNodeId && e.entity_type === 'container' && isKubernetesEntity(e)) {
          node.parentNode = clusterNodeId;
          node.extent = 'parent';
        }

        rfNodes.push(node);
      });
    }

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

    const dependencyEdges = selectedLevel === 'container_level'
      ? generateC4Edges(architecture?.containers || [])
      : [];

    const mergedEdges = [...rfEdges, ...dependencyEdges];

    // Apply layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(rfNodes, mergedEdges);
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
  }, [architecture, selectedLevel, selectedEntityTypes, selectedRelationshipTypes, showExternal, searchTerm, fitView]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data);
  }, []);

  const avgConnections = nodes.length > 0 
    ? (edges.length / nodes.length).toFixed(1)
    : '0';

  const toggleLevel = (level: string) => {
    setSelectedLevel(level);
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
        <h2>Code Architecture Map</h2>
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
                  type="radio"
                  name="c4-level"
                  checked={selectedLevel === level}
                  onChange={() => toggleLevel(level)}
                />
                <span>{level.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
              </label>
            ))}
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
              edgeTypes={edgeTypes}
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
              {selectedNode.type === 'container' && selectedNode.containerMeta && (
                <>
                  {selectedNode.containerMeta.description && (
                    <div className="detail-row">
                      <span className="detail-label">Description:</span>
                      <span className="detail-value">{selectedNode.containerMeta.description}</span>
                    </div>
                  )}
                  <div className="detail-row">
                    <span className="detail-label">Container Type:</span>
                    <span className="detail-value">{selectedNode.containerMeta.container_type || 'Unknown'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Technology:</span>
                    <span className="detail-value">{selectedNode.containerMeta.technology || 'Unknown'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Runtime:</span>
                    <span className="detail-value">{selectedNode.containerMeta.runtime_environment || 'Unknown'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Deployment:</span>
                    <span className="detail-value">{selectedNode.containerMeta.deployment || 'Unknown'}</span>
                  </div>
                  {selectedNode.containerMeta.protocol && (
                    <div className="detail-row">
                      <span className="detail-label">Protocol:</span>
                      <span className="detail-value">{selectedNode.containerMeta.protocol}</span>
                    </div>
                  )}
                  {selectedNode.containerMeta.health_endpoint && (
                    <div className="detail-row">
                      <span className="detail-label">Health Endpoint:</span>
                      <span className="detail-value">{selectedNode.containerMeta.health_endpoint}</span>
                    </div>
                  )}
                  {selectedNode.containerMeta.repository_url && (
                    <div className="detail-row">
                      <span className="detail-label">Repository:</span>
                      <span className="detail-value">{selectedNode.containerMeta.repository_url}</span>
                    </div>
                  )}
                </>
              )}
              {selectedNode.label === 'Kubernetes Cluster' && selectedNode.clusterMeta && (
                <>
                  {selectedNode.clusterMeta.summary && (
                    <div className="detail-row">
                      <span className="detail-label">Summary:</span>
                      <span className="detail-value">
                        {selectedNode.clusterMeta.summary
                          .replace(/<think>.*?<\/think>/gis, '')
                          .replace(/<think>/gi, '')
                          .replace(/\s+/g, ' ')
                          .trim()}
                      </span>
                    </div>
                  )}
                  {selectedNode.clusterMeta.namespaces?.length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">Namespaces:</span>
                      <span className="detail-value">
                        {selectedNode.clusterMeta.namespaces.slice(0, 8).join(', ')}
                        {selectedNode.clusterMeta.namespaces.length > 8 ? '…' : ''}
                      </span>
                    </div>
                  )}
                  {selectedNode.clusterMeta.servers?.length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">Servers:</span>
                      <span className="detail-value">
                        {selectedNode.clusterMeta.servers.slice(0, 5).join(', ')}
                        {selectedNode.clusterMeta.servers.length > 5 ? '…' : ''}
                      </span>
                    </div>
                  )}
                  {selectedNode.clusterMeta.gitops_files?.length > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">GitOps Files:</span>
                      <span className="detail-value">
                        {selectedNode.clusterMeta.gitops_files.slice(0, 6).join(', ')}
                        {selectedNode.clusterMeta.gitops_files.length > 6 ? '…' : ''}
                      </span>
                    </div>
                  )}
                </>
              )}
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
                  <span className="external-badge">External Dependency</span>
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
