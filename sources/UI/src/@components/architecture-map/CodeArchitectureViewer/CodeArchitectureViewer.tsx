import React, { useEffect, useState, useCallback, useRef } from 'react';
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
import ContainerNode from './ContainerNode';

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

const nodeTypes = {
  custom: CustomNode,
  container: ContainerNode,
};

const AVAILABLE_LEVELS = ['context_level', 'container_level', 'component_level', 'code_level'];

// Layout function - grid layout for components in containers
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  if (nodes.length === 0) {
    return { nodes: [], edges };
  }
  
  // Separate parent containers and child nodes
  const containerNodes = nodes.filter(n => n.type === 'container');
  const childNodes = nodes.filter(n => n.parentNode);
  const standaloneNodes = nodes.filter(n => !n.type?.includes('container') && !n.parentNode);
  
  // Layout child nodes within their parent containers
  if (containerNodes.length > 0) {
    // Position containers
    const containerSpacing = 50;
    let currentX = 100;
    
    containerNodes.forEach(container => {
      container.position = { x: currentX, y: 100 };
      
      // Get children of this container
      const children = childNodes.filter(n => n.parentNode === container.id);
      
      // Layout children in a grid inside the container
      const childrenPerRow = 2;
      const childSpacing = 30;
      const childStartX = 40;
      const childStartY = 80;
      
      children.forEach((child, idx) => {
        const row = Math.floor(idx / childrenPerRow);
        const col = idx % childrenPerRow;
        
        child.position = {
          x: childStartX + (col * (220 + childSpacing)),
          y: childStartY + (row * (120 + childSpacing)),
        };
      });
      
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
  // If we have edges, use dagre for layout
  if (edges.length > 0) {
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
      if (nodeWithPosition && nodeWithPosition.x !== undefined && nodeWithPosition.y !== undefined) {
        return {
          ...node,
          position: {
            x: nodeWithPosition.x - 110,
            y: nodeWithPosition.y - 50,
          },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        };
      }
      // Fallback if dagre didn't position this node
      return node;
    });

    return { nodes: layoutedNodes, edges };
  }
  
  // If no edges, use a simple grid layout
  const nodesPerRow = Math.ceil(Math.sqrt(nodes.length));
  const nodeWidth = 220;
  const nodeHeight = 100;
  const spacing = 50;
  
  const layoutedNodes = nodes.map((node, index) => {
    const row = Math.floor(index / nodesPerRow);
    const col = index % nodesPerRow;
    
    return {
      ...node,
      position: {
        x: col * (nodeWidth + spacing) + 100,
        y: row * (nodeHeight + spacing) + 100,
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
  
  // Filters - focus on context-level for manager view
  const [selectedLevel, setSelectedLevel] = useState<string>('context_level');
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<string[]>([]);
  const [selectedRelationshipTypes, setSelectedRelationshipTypes] = useState<string[]>([]);
  const [showExternal, setShowExternal] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  
  const [relationshipTypes, setRelationshipTypes] = useState<string[]>([]);
  const [githubUrl, setGithubUrl] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionStatus, setExtractionStatus] = useState<string | null>(null);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  const applyArchitecture = useCallback((data: any) => {
    // Ensure c4_model_version exists (API might not include it)
    if (!data.c4_model_version) {
      data.c4_model_version = '1.0';
    }
    
    console.log('[CodeArchitectureViewer] Applying cumulative architecture data:', {
      hasSystemContext: !!data.system_context,
      containersCount: data.containers?.length || 0,
      componentsCount: data.components?.length || 0,
      hasRelationships: !!data.relationships,
      extractionMode: data.metadata?.extraction_mode || 'unknown',
    });
    
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
          languages: data.system_context?.languages,
          frameworks: data.system_context?.frameworks,
          repository_url: data.system_context?.repository_url,
          git: data.system_context?.git,
          context_sources: data.system_context?.context_sources,
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
          is_external: true,
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
    setSelectedNode(null);
    
    console.log('[CodeArchitectureViewer] Architecture state set:', {
      contextLevel: data.context_level?.entities?.length || 0,
      containerLevel: data.container_level?.entities?.length || 0,
      componentLevel: data.component_level?.entities?.length || 0,
      codeLevel: data.code_level?.entities?.length || 0,
      hasSystemContext: !!data.system_context,
      containersCount: data.containers?.length || 0,
      componentsCount: data.components?.length || 0,
    });
    
    // Extract unique entity and relationship types
    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];
    const levelsForFilters = ['context_level', 'container_level', 'component_level', 'code_level'];
    
    levelsForFilters.forEach(level => {
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
  }, []);

  // Load architecture data
  useEffect(() => {
    const loadArchitecture = async () => {
      try {
        setLoading(true);
        const data = await codeArchitectureAPI.getArchitecture();
        applyArchitecture(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load architecture');
      } finally {
        setLoading(false);
      }
    };
    
    loadArchitecture();
  }, [applyArchitecture]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  const handleExtractFromGithub = useCallback(async () => {
    if (!githubUrl.trim()) {
      setExtractionError('Please enter a GitHub URL');
      return;
    }

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setExtractionError(null);
    setExtractionStatus('Starting extraction...');
    setIsExtracting(true);

    try {
      const response = await codeArchitectureAPI.extractFromGitHub(githubUrl.trim(), true);
      const taskId = response.task_id;

      if (!taskId) {
        throw new Error('No task id returned from extraction');
      }

      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const status = await codeArchitectureAPI.getExtractionStatus(taskId);
          const progress = typeof status.progress === 'number'
            ? Math.round(status.progress * 100)
            : null;
          const statusLabel = status.message || status.status;
          setExtractionStatus(progress !== null ? `${statusLabel} (${progress}%)` : statusLabel);

          if (status.status === 'completed') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionStatus('Extraction completed');

            const results = await codeArchitectureAPI.getExtractionResults(taskId);
            if (results) {
              console.log('[CodeArchitectureViewer] Extraction results received:', results);
              applyArchitecture(results);
              setSelectedLevel('context_level');
            }
          } else if (status.status === 'failed') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionError(status.message || 'Extraction failed');
          }
        } catch (pollError) {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsExtracting(false);
          setExtractionError('Failed to poll extraction status');
        }
      }, 2000);
    } catch (err) {
      setIsExtracting(false);
      setExtractionError(err instanceof Error ? err.message : 'Failed to start extraction');
    }
  }, [githubUrl, applyArchitecture]);

  // Process architecture data into graph format
  useEffect(() => {
    if (!architecture) {
      console.log('[CodeArchitectureViewer] No architecture data available');
      return;
    }

    console.log('[CodeArchitectureViewer] Processing graph for level:', selectedLevel, {
      hasContextLevel: !!architecture.context_level,
      hasContainerLevel: !!architecture.container_level,
      hasComponentLevel: !!architecture.component_level,
      hasCodeLevel: !!architecture.code_level,
    });

    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];

    // Collect entities and relationships from the selected level
    if (architecture[selectedLevel as keyof C4Architecture]) {
      const levelData = architecture[selectedLevel as keyof C4Architecture] as C4Level;
      console.log('[CodeArchitectureViewer] Level data found:', {
        entitiesCount: levelData.entities?.length || 0,
        relationshipsCount: levelData.relationships?.length || 0,
      });
      if (levelData.entities) {
        // Add level metadata to each entity
        allEntities.push(...levelData.entities.map(e => ({ ...e, level: selectedLevel })));
      }
      if (levelData.relationships) {
        allRelationships.push(...levelData.relationships);
      }
    } else {
      console.warn('[CodeArchitectureViewer] No data found for selected level:', selectedLevel);
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
              attributes: e.attributes,
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
            attributes: e.attributes,
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
          const rows = Math.ceil(kubernetesContainers.length / 2);
          const clusterHeight = Math.max(520, rows * 150 + 140);
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
              width: Math.max(900, kubernetesContainers.length * 240),
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
            attributes: e.attributes,
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

    // Apply layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(rfNodes, rfEdges);
    
    // Ensure all nodes have valid positions (not all at 0,0)
    const nodesWithValidPositions = layoutedNodes.map((node, idx) => {
      // If node is at origin and there are multiple nodes, it likely wasn't positioned correctly
      if (node.position.x === 0 && node.position.y === 0 && layoutedNodes.length > 1) {
        // Use a simple grid fallback
        const nodesPerRow = Math.ceil(Math.sqrt(layoutedNodes.length));
        const row = Math.floor(idx / nodesPerRow);
        const col = idx % nodesPerRow;
        return {
          ...node,
          position: {
            x: col * 280 + 100,
            y: row * 150 + 100,
          },
        };
      }
      return node;
    });
    
    console.log('[CodeArchitectureViewer] Graph nodes/edges created:', {
      nodesCount: nodesWithValidPositions.length,
      edgesCount: layoutedEdges.length,
      selectedLevel,
      filteredEntitiesCount: filteredEntities.length,
      filteredRelationshipsCount: filteredRelationships.length,
      sampleNodePositions: nodesWithValidPositions.slice(0, 5).map(n => ({ 
        id: n.id, 
        type: n.type,
        pos: n.position,
        hasData: !!n.data,
        label: n.data?.label 
      })),
      allNodesAtOrigin: nodesWithValidPositions.every(n => n.position.x === 0 && n.position.y === 0),
    });
    
    setNodes(nodesWithValidPositions);
    setEdges(layoutedEdges);
    
    // Fit view after layout to show entire graph
    // Use multiple attempts to ensure fitView works
    if (layoutedNodes.length > 0) {
      window.requestAnimationFrame(() => {
        setTimeout(() => {
          try {
            fitView({
              padding: 50,
              includeHiddenNodes: false,
              duration: 500,
              maxZoom: 1.5,
              minZoom: 0.1,
            });
          } catch (e) {
            console.warn('[CodeArchitectureViewer] fitView error:', e);
          }
        }, 200);
        
        // Try again after a longer delay to ensure nodes are rendered
        setTimeout(() => {
          try {
            fitView({
              padding: 50,
              includeHiddenNodes: false,
              duration: 300,
              maxZoom: 1.5,
              minZoom: 0.1,
            });
          } catch (e) {
            console.warn('[CodeArchitectureViewer] fitView retry error:', e);
          }
        }, 500);
      });
    }
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

  const systemAttributes = selectedNode?.type === 'system'
    ? (selectedNode.attributes || {})
    : null;

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
          <p className="hint">Run extraction above or execute <code>python -m services.code_extraction.c4_extractor</code></p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-architecture-viewer">
      <div className="viewer-header">
        <h2>Architecture Context (Multi-Repository)</h2>
        <p>Cumulative view of all added repositories - add multiple projects to see complete landscape</p>
      </div>

      <div className="viewer-layout">
        <aside className="filters-sidebar">
          <div className="filter-section">
            <h3>Extract Context</h3>
            <input
              type="text"
              placeholder="https://github.com/owner/repo"
              value={githubUrl}
              onChange={e => setGithubUrl(e.target.value)}
              className="search-input"
            />
            <div className="button-group">
              <button
                className="fit-button"
                onClick={handleExtractFromGithub}
                disabled={isExtracting}
              >
                {isExtracting ? 'Extracting...' : 'Add Repository'}
              </button>
              <button
                className="reset-button"
                onClick={async () => {
                  if (confirm('⚠️ Clear ALL repositories and start fresh? This will remove all accumulated architecture data.')) {
                    try {
                      await codeArchitectureAPI.clearArchitecture();
                      setArchitecture(null);
                      setNodes([]);
                      setEdges([]);
                      setGithubUrl('');
                      setExtractionStatus('All repositories cleared - ready for fresh extraction');
                      setExtractionError('');
                    } catch (err) {
                      setExtractionError('Failed to clear data');
                    }
                  }
                }}
                disabled={isExtracting}
                title="Clear all repositories and start fresh"
              >
                Clear All
              </button>
            </div>
            {extractionStatus && (
              <div className="extract-status">{extractionStatus}</div>
            )}
            {extractionError && (
              <div className="extract-error">{extractionError}</div>
            )}
            {architecture && (
              <div className="extract-info">
                <small>💡 Data accumulates - add multiple repos to build complete architecture view</small>
              </div>
            )}
          </div>

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
            {AVAILABLE_LEVELS.map(level => (
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
            <div style={{ width: '100%', height: '100%' }}>
              <ReactFlow
                key={`${selectedLevel}-${nodes.length}-${edges.length}`}
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
                attributionPosition="bottom-left"
                defaultViewport={{ x: 0, y: 0, zoom: 1.5 }}
                minZoom={0.2}
                maxZoom={5.0}
              >
                <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e0e0e0" />
                <Controls />
              </ReactFlow>
            </div>
          )}
        </main>

        {selectedNode && (
          <aside className="node-details-panel">
            <div className="panel-header">
              <h3>{selectedNode.fullName || selectedNode.label}</h3>
              <button className="close-btn" onClick={() => setSelectedNode(null)}>×</button>
            </div>
            <div className="panel-content">
              {/* One-sentence description (LLM-generated purpose or description) */}
              {(systemAttributes?.purpose || selectedNode.containerMeta?.description || selectedNode.documentation) && (
                <div className="detail-row description-row">
                  <span className="detail-value description-text">
                    {systemAttributes?.purpose || selectedNode.containerMeta?.description || selectedNode.documentation || 'No description available'}
                  </span>
                </div>
              )}

              {/* Domain field (from image: business bucket) */}
              {systemAttributes?.business_domain && (
                <div className="detail-row">
                  <span className="detail-label">domain</span>
                  <span className="detail-value">{systemAttributes.business_domain}</span>
                </div>
              )}

              {/* Owner field */}
              {(systemAttributes?.owner_team || selectedNode.containerMeta?.owner) && (
                <div className="detail-row">
                  <span className="detail-label">owner</span>
                  <span className="detail-value">{systemAttributes?.owner_team || selectedNode.containerMeta?.owner || 'No owner listed'}</span>
                </div>
              )}

              {/* Status field (maps to tier/criticality) */}
              {systemAttributes?.criticality && (
                <div className="detail-row">
                  <span className="detail-label">status</span>
                  <span className="detail-value status-badge">{systemAttributes.criticality}</span>
                </div>
              )}

              {/* Data class field (sensitivity) */}
              {(systemAttributes?.data_class || selectedNode.attributes?.data_class) && (
                <div className="detail-row">
                  <span className="detail-label">data_class</span>
                  <span className="detail-value">{systemAttributes?.data_class || selectedNode.attributes?.data_class}</span>
                </div>
              )}

              {/* Additional metadata for context */}
              {selectedNode.type && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">Type:</span>
                  <span className="detail-value">{selectedNode.type}</span>
                </div>
              )}
              
              {selectedNode.containerMeta?.technology && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">Technology:</span>
                  <span className="detail-value">{selectedNode.containerMeta.technology}</span>
                </div>
              )}

              {selectedNode.file && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">File:</span>
                  <span className="detail-value file-path">{selectedNode.file}</span>
                </div>
              )}

              {/* Show URL for external services */}
              {selectedNode.attributes?.url && (
                <div className="detail-row">
                  <span className="detail-label">url</span>
                  <span className="detail-value">
                    <a href={selectedNode.attributes.url} target="_blank" rel="noopener noreferrer" className="external-link">
                      {selectedNode.attributes.url}
                    </a>
                  </span>
                </div>
              )}

              {selectedNode.attributes?.detected_from && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">Detected from:</span>
                  <span className="detail-value">{selectedNode.attributes.detected_from}</span>
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
