import React, { useEffect, useState, useCallback, useRef } from 'react';
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
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import './CodeArchitectureViewer.scss';
import { codeArchitectureAPI } from '../../../services/api';
import CustomNode from './CustomNode';
import ContainerNode from './ContainerNode';
import C4Edge from './C4Edge';
import BatchUrlInput from './batchurlinput';
import GitHubOrgScanner from './githuborgscanner';

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
  containers?: any[]; // Array format from backend
  components?: any[]; // Array format from backend
  relationships?: C4Relationships;
  metadata?: {
    runtime?: {
      platform?: string;
      cluster?: any;
    };
  };
  context_level?: C4Level;
  container_level?: C4Level; // Transformed format
  component_level?: C4Level; // Transformed format
  code_level?: C4Level;
}

const edgeTypes = {
  C4Edge,
};

const buildContainerId = (container: any, idx: number) =>
  `container_${container.name || idx}`;

const generateC4Edges = (containers: any[] = [], relationships: any[] = []): Edge[] => {
  const nameToId = new Map<string, string>();
  const edges: Edge[] = [];
  const relationshipEdgesAdded = new Set<string>();

  containers.forEach((container, idx) => {
    if (container?.name) {
      nameToId.set(container.name, buildContainerId(container, idx));
    }
  });

  relationships.forEach((rel, idx) => {
    const sourceName = rel?.from ?? rel?.source;
    const targetName = rel?.to ?? rel?.destination;
    if (!sourceName || !targetName) {
      return;
    }

    const sourceId = nameToId.get(String(sourceName));
    const targetId = nameToId.get(String(targetName));
    if (!sourceId || !targetId) {
      return;
    }

    const relationshipKey = `${sourceId}-${targetId}`;
    if (relationshipEdgesAdded.has(relationshipKey)) {
      return;
    }

    const protocol = typeof rel?.protocol === 'string' ? rel.protocol.trim() : '';
    const label = protocol ? protocol.toUpperCase() : undefined;
    const edgeId = `c4-rel-${sourceId}-${targetId}-${idx}`;

    edges.push({
      id: edgeId,
      source: sourceId,
      target: targetId,
      label,
      type: 'C4Edge',
      interactionWidth: 16,
      markerEnd: {
        type: MarkerType.ArrowClosed,
      },
      data: {
        description: rel?.description || rel?.llm_description,
        llm_description: rel?.llm_description,
        protocol: protocol || undefined,
        relationship_type: rel?.relationship_type || rel?.type,
      },
    });

    relationshipEdgesAdded.add(relationshipKey);
  });

  if (relationships.length > 0) {
    return edges;
  }

  containers.forEach((container, idx) => {
    const sourceId = buildContainerId(container, idx);
    const protocol =
      typeof container?.protocol === 'string' ? container.protocol.trim() : '';
    const label = protocol ? protocol.toUpperCase() : undefined;
    const dependencies: string[] = Array.isArray(
      container?.dependencies_internal
    )
      ? container.dependencies_internal.map((dependency: unknown) =>
          String(dependency)
        )
      : [];

    dependencies.forEach((dependencyName: string, depIdx: number) => {
      const targetId = nameToId.get(String(dependencyName));
      if (!targetId) {
        return;
      }

      if (relationshipEdgesAdded.has(`${sourceId}-${targetId}`)) {
        return;
      }

      edges.push({
        id: `c4-edge-${sourceId}-${targetId}-${depIdx}`,
        source: sourceId,
        target: targetId,
        label,
        type: 'C4Edge',
        interactionWidth: 16,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
        data: {
          protocol,
          relationship_type: 'uses',
        },
      });
    });
  });

  return edges;
};

const normalizeDescription = (text?: string) => {
  if (!text) return '';
  return text.replace(/\s+/g, ' ').trim();
};

const nodeTypes = {
  custom: CustomNode,
  container: ContainerNode,
};

const AVAILABLE_LEVELS = [
  'context_level',
  'container_level',
  'component_level',
  'code_level',
];

// Layout function - grid layout for components in containers
const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = 'LR'
) => {
  if (nodes.length === 0) {
    return { nodes: [], edges };
  }

  // Separate parent containers and child nodes
  const containerNodes = nodes.filter(n => n.type === 'container');
  const childNodes = nodes.filter(n => n.parentNode);
  const standaloneNodes = nodes.filter(
    n => !n.type?.includes('container') && !n.parentNode
  );

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
          x: childStartX + col * (childNodeWidth + childSpacing),
          y: childStartY + row * (childNodeHeight + childSpacing),
        };
        child.sourcePosition = Position.Right;
        child.targetPosition = Position.Left;
      });

      if (children.length > 0) {
        const rows = Math.ceil(children.length / childrenPerRow);
        const contentWidth =
          childStartX * 2 +
          childrenPerRow * childNodeWidth +
          (childrenPerRow - 1) * childSpacing;
        const contentHeight =
          childStartY + rows * childNodeHeight + (rows - 1) * childSpacing + 50;

        container.style = {
          ...container.style,
          width: Math.max(640, contentWidth),
          height: Math.max(420, contentHeight),
        };
      }

      currentX +=
        ((container.style?.width as number) || 700) + containerSpacing;
    });

    return {
      nodes: [...containerNodes, ...childNodes, ...standaloneNodes],
      edges,
    };
  }

  // Check if we have components without relationships (independent endpoints)
  const hasRelationships = edges.length > 0;

  if (!hasRelationships && nodes.length > 0) {
    // Grid layout for independent components
    const methodGroups = new Map<string, Node[]>();
    nodes.forEach(node => {
      const method =
        node.data.type === 'component'
          ? node.data.fullName?.split(' ')[0] || 'OTHER'
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

    const layoutedNodes = nodes.map(node => {
      const method =
        node.data.type === 'component'
          ? node.data.fullName?.split(' ')[0] || 'OTHER'
          : 'OTHER';

      const methodIndex = methodOrder.indexOf(method);
      const groupNodes = methodGroups.get(method) || [];
      const nodeIndex = groupNodes.indexOf(node);

      return {
        ...node,
        position: {
          x: columnX + methodIndex * columnWidth,
          y: 100 + nodeIndex * rowHeight,
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

    nodes.forEach(node => {
      dagreGraph.setNode(node.id, {
        width: 220,
        height: 100,
      });
    });

    edges.forEach(edge => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map(node => {
      const nodeWithPosition = dagreGraph.node(node.id);
      if (
        nodeWithPosition &&
        nodeWithPosition.x !== undefined &&
        nodeWithPosition.y !== undefined
      ) {
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
  const [selectedRelationshipTypes, setSelectedRelationshipTypes] = useState<
    string[]
  >([]);
  const [showExternal, setShowExternal] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [nodeDescription, setNodeDescription] = useState<string>('');
  const [edgeDescription, setEdgeDescription] = useState<string>('');
  const [isNodeLoading, setIsNodeLoading] = useState(false);
  const [isEdgeLoading, setIsEdgeLoading] = useState(false);
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

    console.log(
      '[CodeArchitectureViewer] Applying cumulative architecture data:',
      {
        hasSystemContext: !!data.system_context,
        containersCount: data.containers?.length || 0,
        componentsCount: data.components?.length || 0,
        hasRelationships: !!data.relationships,
        extractionMode: data.metadata?.extraction_mode || 'unknown',
      }
    );

    // Transform containers array into container_level structure
    if (data.containers && Array.isArray(data.containers)) {
      const sysCtx = data.system_context || {};
      const inheritedAttrs = {
        owner: sysCtx.owner_team || sysCtx.owner,
        domain: sysCtx.business_domain || sysCtx.domain,
        status: sysCtx.status,
        tier: sysCtx.criticality || sysCtx.tier,
        data_class: sysCtx.data_class,
        active_experts: sysCtx.active_experts,
        compliance: sysCtx.compliance,
      };
      const containerEntities: CodeEntity[] = data.containers.map(
        (container: any, idx: number) => ({
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
            description: container.description,
            technology: container.technology,
            repository_url: container.repository_url,
            health_endpoint: container.health_endpoint,
            ...inheritedAttrs,
          },
        })
      );

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
          const sourceName = (rel as any).from ?? rel.source;
          const targetName = (rel as any).to ?? rel.destination;
          const sourceId = sourceName ? containerIdByName.get(String(sourceName)) : undefined;
          const targetId = targetName ? containerIdByName.get(String(targetName)) : undefined;

          if (sourceId && targetId) {
            containerRelationships.push({
              id: `rel_container_${idx}`,
              source_entity_id: sourceId,
              target_entity_id: targetId,
              relationship_type: rel.relationship_type || (rel as any).type || 'depends_on',
              attributes: {
                description: rel.description || (rel as any).llm_description,
                protocol: (rel as any).protocol,
              },
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
          owner: data.system_context?.owner,
          owner_contributors: data.system_context?.owner_contributors,
          owner_contributor_stats: data.system_context?.owner_contributor_stats,
          business_domain: data.system_context?.business_domain,
          domain: data.system_context?.domain,
          criticality: data.system_context?.criticality,
          tier: data.system_context?.tier,
          status: data.system_context?.status,
          data_class: data.system_context?.data_class,
          active_experts: data.system_context?.active_experts,
          compliance: data.system_context?.compliance,
          purpose: data.system_context?.purpose,
          languages: data.system_context?.languages,
          frameworks: data.system_context?.frameworks,
          repository_url: data.system_context?.repository_url,
          git: data.system_context?.git,
          context_sources: data.system_context?.context_sources,
        },
      });

      const actorEntities = (data.system_context?.actors || []).map(
        (actor: any, idx: number) => ({
          id: `context_actor_${idx}`,
          name: actor.name || `Actor ${idx + 1}`,
          entity_type: actor.type || 'person',
          language: 'Unknown',
          file_path: '',
          attributes: {},
        })
      );

      const externalEntities = (
        data.system_context?.external_dependencies || []
      ).map((dep: any, idx: number) => ({
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
        data.relationships.context.forEach(
          (rel: C4DiagramRelationship, idx: number) => {
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
          }
        );
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

      const sysCtxForComponents = data.system_context || {};
      const inheritedForComponents = {
        owner: sysCtxForComponents.owner_team || sysCtxForComponents.owner,
        domain:
          sysCtxForComponents.business_domain || sysCtxForComponents.domain,
        status: sysCtxForComponents.status,
        tier: sysCtxForComponents.criticality || sysCtxForComponents.tier,
        data_class: sysCtxForComponents.data_class,
        active_experts: sysCtxForComponents.active_experts,
        compliance: sysCtxForComponents.compliance,
      };
      data.components.forEach((component: any, groupIdx: number) => {
        // Check if this is a component group
        if (
          component.type === 'component_group' &&
          component.components &&
          Array.isArray(component.components)
        ) {
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
                ...inheritedForComponents,
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
              ...inheritedForComponents,
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
    const levelsForFilters = [
      'context_level',
      'container_level',
      'component_level',
      'code_level',
    ];

    levelsForFilters.forEach(level => {
      if (data[level as keyof C4Architecture]) {
        const levelData = data[level as keyof C4Architecture] as C4Level;
        if (levelData.entities) allEntities.push(...levelData.entities);
        if (levelData.relationships)
          allRelationships.push(...levelData.relationships);
      }
    });

    const uniqueEntityTypes = Array.from(
      new Set(allEntities.map(e => e.entity_type))
    );
    const uniqueRelTypes = Array.from(
      new Set(allRelationships.map(r => r.relationship_type))
    );

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
        setError(
          err instanceof Error ? err.message : 'Failed to load architecture'
        );
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
      const response = await codeArchitectureAPI.extractFromGitHub(
        githubUrl.trim(),
        true
      );
      const taskId = response.task_id;

      if (!taskId) {
        throw new Error('No task id returned from extraction');
      }

      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const status = await codeArchitectureAPI.getExtractionStatus(taskId);
          const progress =
            typeof status.progress === 'number'
              ? Math.round(status.progress * 100)
              : null;
          const statusLabel = status.message || status.status;
          setExtractionStatus(
            progress !== null ? `${statusLabel} (${progress}%)` : statusLabel
          );

          if (status.status === 'completed') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionStatus('Extraction completed');

            const results =
              await codeArchitectureAPI.getExtractionResults(taskId);
            if (results) {
              console.log(
                '[CodeArchitectureViewer] Extraction results received:',
                results
              );
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
      setExtractionError(
        err instanceof Error ? err.message : 'Failed to start extraction'
      );
    }
  }, [githubUrl, applyArchitecture]);

  // Batch extraction handler
  const handleBatchExtract = useCallback(
    async (urls: string[]) => {
      if (urls.length === 0) return;

      setIsExtracting(true);
      setExtractionError(null);

      // Sequential extraction to avoid overwhelming backend
      for (let i = 0; i < urls.length; i++) {
        const url = urls[i];
        setExtractionStatus(
          `Extracting ${i + 1}/${urls.length}: ${url.replace('https://github.com/', '')}`
        );

        try {
          const response = await codeArchitectureAPI.extractFromGitHub(
            url,
            true,
            true
          );
          const taskId = response.task_id;

          // Poll for completion
          let completed = false;
          while (!completed) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            const status =
              await codeArchitectureAPI.getExtractionStatus(taskId);

            const progress =
              typeof status.progress === 'number'
                ? Math.round(status.progress * 100)
                : null;

            setExtractionStatus(
              `Extracting ${i + 1}/${urls.length}: ${url.replace('https://github.com/', '')} ${progress !== null ? `(${progress}%)` : ''}`
            );

            if (status.status === 'completed') {
              completed = true;
            } else if (status.status === 'failed') {
              throw new Error(status.message || 'Extraction failed');
            }
          }
        } catch (err) {
          console.error(`Failed on ${url}:`, err);
          setExtractionError(
            `Failed on ${url}: ${err instanceof Error ? err.message : 'Unknown error'}`
          );
          // Continue with remaining URLs
        }
      }

      setIsExtracting(false);
      setExtractionStatus(
        `Batch extraction completed - ${urls.length} repositories analyzed`
      );

      // Reload architecture data
      try {
        const data = await codeArchitectureAPI.getArchitecture();
        applyArchitecture(data);
        setSelectedLevel('context_level');
      } catch (err) {
        console.error('Failed to reload architecture:', err);
      }
    },
    [applyArchitecture]
  );

  // GitHub organization scan handler
  const handleGitHubOrgScan = useCallback(
    async (
      username: string,
      options: { includeForks: boolean; maxRepos: number }
    ) => {
      setIsExtracting(true);
      setExtractionError(null);
      setExtractionStatus(`Scanning ${username} for repositories...`);

      try {
        const response = await codeArchitectureAPI.extractFromGitHubOrg(
          username,
          options.includeForks,
          options.maxRepos,
          true // append_mode
        );

        const taskId = response.task_id;

        // Poll for batch completion
        const pollInterval = setInterval(async () => {
          try {
            const status =
              await codeArchitectureAPI.getExtractionStatus(taskId);

            const progress =
              typeof status.progress === 'number'
                ? Math.round(status.progress * 100)
                : null;

            const completed = (status as any).completed_repos || 0;
            const total = (status as any).total_repos || options.maxRepos;

            setExtractionStatus(
              `Extracting ${completed}/${total} repositories... ${progress !== null ? `(${progress}%)` : ''}`
            );

            if (status.status === 'completed') {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionStatus(
                `GitHub org scan completed - ${total} repositories analyzed`
              );

              // Reload architecture
              const data = await codeArchitectureAPI.getArchitecture();
              applyArchitecture(data);
              setSelectedLevel('context_level');
            } else if (status.status === 'failed') {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionError(status.message || 'GitHub org scan failed');
            }
          } catch (pollError) {
            clearInterval(pollInterval);
            setIsExtracting(false);
            setExtractionError('Failed to poll extraction status');
          }
        }, 3000); // Poll every 3 seconds for batch operations
      } catch (err) {
        setIsExtracting(false);
        const errorMessage =
          err instanceof Error
            ? err.message
            : 'Failed to scan GitHub organization';
        setExtractionError(errorMessage);
      }
    },
    [applyArchitecture]
  );

  // Process architecture data into graph format
  useEffect(() => {
    if (!architecture) {
      console.log('[CodeArchitectureViewer] No architecture data available');
      return;
    }

    console.log(
      '[CodeArchitectureViewer] Processing graph for level:',
      selectedLevel,
      {
        hasContextLevel: !!architecture.context_level,
        hasContainerLevel: !!architecture.container_level,
        hasComponentLevel: !!architecture.component_level,
        hasCodeLevel: !!architecture.code_level,
      }
    );

    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];

    // Collect entities and relationships from the selected level
    if (architecture[selectedLevel as keyof C4Architecture]) {
      const levelData = architecture[
        selectedLevel as keyof C4Architecture
      ] as C4Level;
      console.log('[CodeArchitectureViewer] Level data found:', {
        entitiesCount: levelData.entities?.length || 0,
        relationshipsCount: levelData.relationships?.length || 0,
      });
      if (levelData.entities) {
        // Add level metadata to each entity
        allEntities.push(
          ...levelData.entities.map(e => ({ ...e, level: selectedLevel }))
        );
      }
      if (levelData.relationships) {
        allRelationships.push(...levelData.relationships);
      }
    } else {
      console.warn(
        '[CodeArchitectureViewer] No data found for selected level:',
        selectedLevel
      );
    }

    // Fallback: build minimal level data if the backend didn't provide it
    if (allEntities.length === 0 && selectedLevel === 'container_level' && architecture.containers?.length) {
      const fallbackContainers = architecture.containers.map((container: any, idx: number) => ({
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
        level: selectedLevel,
      }));
      allEntities.push(...fallbackContainers);
    }

    if (allEntities.length === 0 && selectedLevel === 'context_level' && architecture.system_context) {
      const systemName = architecture.system_context?.name || 'System';
      allEntities.push({
        id: `context_system_${systemName}`,
        name: systemName,
        entity_type: 'system',
        language: 'Unknown',
        file_path: '',
        attributes: {
          owner_team: architecture.system_context?.owner_team,
          business_domain: architecture.system_context?.business_domain,
          criticality: architecture.system_context?.criticality,
          purpose: architecture.system_context?.purpose,
        },
        level: selectedLevel,
      });
    }

    // Filter entities
    let filteredEntities = allEntities.filter(e => {
      const typeMatch =
        selectedEntityTypes.length === 0 ||
        selectedEntityTypes.includes(e.entity_type);
      const externalMatch = showExternal || !e.attributes?.is_external;
      const searchMatch =
        searchTerm === '' ||
        e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        e.file_path?.toLowerCase().includes(searchTerm.toLowerCase());

      return typeMatch && externalMatch && searchMatch;
    });

    // Create entity lookup
    const entityIds = new Set(filteredEntities.map(e => e.id));

    // Filter relationships
    const filteredRelationships = allRelationships.filter(r => {
      const typeMatch =
        selectedRelationshipTypes.length === 0 ||
        selectedRelationshipTypes.includes(r.relationship_type);
      const validSource = entityIds.has(r.source_entity_id);
      const validTarget =
        r.target_entity_id && entityIds.has(r.target_entity_id);

      return typeMatch && validSource && validTarget;
    });

    // Convert to React Flow format
    const rfNodes: Node[] = [];

    // If we're showing components, create container frames based on their actual container assignment
    if (
      selectedLevel === 'component_level' &&
      filteredEntities.some(e => e.entity_type === 'component')
    ) {
      const componentEntities = filteredEntities.filter(
        e => e.entity_type === 'component'
      );

      // Group components by their actual container attribute
      const containerGroups = new Map<string, typeof componentEntities>();
      componentEntities.forEach(comp => {
        const containerName =
          (comp.attributes?.container as string) || 'Unknown';

        if (!containerGroups.has(containerName)) {
          containerGroups.set(containerName, []);
        }
        containerGroups.get(containerName)!.push(comp);
      });

      // Create container frames for each group
      let currentX = 100;
      containerGroups.forEach((components, containerName) => {
        // Find the actual container info from architecture data
        const containerInfo = architecture?.containers?.find(
          (c: any) => c.name === containerName
        );
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

          const typeSuffixes = [
            'Class',
            'Function',
            'Method',
            'Module',
            'File',
            'Variable',
            'Constant',
          ];
          typeSuffixes.forEach(suffix => {
            if (shortName.endsWith(suffix) && shortName !== suffix) {
              shortName = shortName.slice(0, -suffix.length);
            }
          });

          shortName = shortName.replace(/[._]+$/, '');
          const displayType =
            e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);

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
              x: childStartX + col * (220 + childSpacing),
              y: childStartY + row * (120 + childSpacing),
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
      const nonComponents = filteredEntities.filter(
        e => e.entity_type !== 'component'
      );
      nonComponents.forEach(e => {
        let shortName = e.name.includes('.')
          ? e.name.split('.').pop() || e.name
          : e.name;

        const typeSuffixes = [
          'Class',
          'Function',
          'Method',
          'Module',
          'File',
          'Variable',
          'Constant',
        ];
        typeSuffixes.forEach(suffix => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });

        shortName = shortName.replace(/[._]+$/, '');
        const displayType =
          e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);

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
      const containerEntities = filteredEntities.filter(
        e => e.entity_type === 'container'
      );
      const containerInfoByName = new Map(
        (architecture?.containers || []).map((container: any) => [
          container.name,
          container,
        ])
      );

      const isKubernetesEntity = (entity: CodeEntity) => {
        const tech = String(entity.language || '').toLowerCase();
        const containerType = String(
          entity.attributes?.container_type || ''
        ).toLowerCase();
        const runtimeEnv = String(
          entity.attributes?.runtime_environment || ''
        ).toLowerCase();
        const deployment = String(
          entity.attributes?.deployment || ''
        ).toLowerCase();

        return (
          tech.includes('kubernetes') ||
          containerType.includes('helm') ||
          containerType.includes('kubernetes') ||
          runtimeEnv.includes('kubernetes') ||
          deployment.includes('helm') ||
          deployment.includes('kustomize') ||
          deployment.includes('manifest')
        );
      };

      let clusterNodeId: string | null = null;

      if (hasContainerLevel && containerEntities.length > 0) {
        const kubernetesContainers =
          containerEntities.filter(isKubernetesEntity);

        if (kubernetesContainers.length > 0) {
          const columns = Math.min(
            4,
            Math.max(2, Math.ceil(kubernetesContainers.length / 2))
          );
          const rows = Math.ceil(kubernetesContainers.length / columns);
          const clusterWidth = Math.max(720, columns * 240 + 200);
          const clusterHeight = Math.max(420, rows * 140 + 180);
          const clusterMeta = architecture?.metadata?.runtime?.cluster;
          clusterNodeId = 'cluster_kubernetes';
          rfNodes.push({
            id: clusterNodeId,
            type: 'container',
            position: { x: 80, y: 80 },
            className: 'cluster-frame',
            draggable: false,
            selectable: false,
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
              pointerEvents: 'none',
            },
          });
        }
      }

      // Original logic for non-component entities
      filteredEntities.forEach(e => {
        let shortName = e.name.includes('.')
          ? e.name.split('.').pop() || e.name
          : e.name;

        const typeSuffixes = [
          'Class',
          'Function',
          'Method',
          'Module',
          'File',
          'Variable',
          'Constant',
        ];
        typeSuffixes.forEach(suffix => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });

        shortName = shortName.replace(/[._]+$/, '');
        const displayType =
          e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);

        const containerInfo =
          e.entity_type === 'container'
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
              llm_description: containerInfo.llm_description,
              health_endpoint: containerInfo.health_endpoint,
              repository_url: containerInfo.repository_url,
            } : undefined,
          },
        };

        if (
          clusterNodeId &&
          e.entity_type === 'container' &&
          isKubernetesEntity(e)
        ) {
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
        interactionWidth: 16,
        style: { 
          stroke: '#b0bec5', 
          strokeWidth: 2,
        },
        data: {
          description: r.attributes?.description,
          relationship_type: r.relationship_type,
        },
        // Remove labels for cleaner look
        // label: r.relationship_type,
      }));

    const dependencyEdges = selectedLevel === 'container_level'
      ? generateC4Edges(
          architecture?.containers || [],
          architecture?.relationships?.containers || []
        )
      : [];

    const mergedEdges = [...rfEdges, ...dependencyEdges];

    // Apply layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      rfNodes,
      mergedEdges
    );

    // Ensure all nodes have valid positions (not all at 0,0)
    const nodesWithValidPositions = layoutedNodes.map((node, idx) => {
      if (
        node.position.x === 0 &&
        node.position.y === 0 &&
        layoutedNodes.length > 1
      ) {
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

    setNodes(nodesWithValidPositions);
    setEdges(layoutedEdges);

    // Fit view after layout to show entire graph
    // Use multiple attempts to ensure fitView works
    if (layoutedNodes.length > 0) {
      window.requestAnimationFrame(() => {
        // Progressive fitting for better rendering
        const attemptFitView = (delay: number, attempt: number = 1) => {
          setTimeout(() => {
            try {
              fitView({
                padding: 25,
                includeHiddenNodes: false,
                duration: attempt === 1 ? 600 : 400,
                maxZoom: 2.5,
                minZoom: 0.3,
              });
            } catch (e) {
              console.warn(`[CodeArchitectureViewer] fitView attempt ${attempt} error:`, e);
            }
          }, delay);
        };

        // Multiple attempts with increasing delays for large graphs
        attemptFitView(300, 1);
        attemptFitView(800, 2);
        attemptFitView(1500, 3); // Final attempt for very large graphs
      });
    }
  }, [
    architecture,
    selectedLevel,
    selectedEntityTypes,
    selectedRelationshipTypes,
    showExternal,
    searchTerm,
    fitView,
  ]);

  const onNodeClick = useCallback(async (_event: React.MouseEvent, node: Node) => {
    setSelectedEdge(null);
    setEdgeDescription('');
    setSelectedNode(node.data);
    setNodeDescription('');
    const precomputedDescription =
      node.data?.containerMeta?.llm_description ||
      node.data?.containerMeta?.description ||
      node.data?.llm_description ||
      node.data?.attributes?.llm_description;

    const normalizedPrecomputed = normalizeDescription(precomputedDescription);
    if (normalizedPrecomputed) {
      setNodeDescription(normalizedPrecomputed);
      setIsNodeLoading(false);
      return;
    }

    setIsNodeLoading(true);

    try {
      const response = await codeArchitectureAPI.describeNode({
        id: node.id,
        name: node.data?.fullName || node.data?.label,
        type: node.data?.type,
        level: node.data?.level,
        attributes: node.data?.attributes,
        containerMeta: node.data?.containerMeta,
        file: node.data?.file,
      });
      const normalizedResponse = normalizeDescription(response?.description);
      setNodeDescription(normalizedResponse || 'No description available.');
    } catch (error) {
      setNodeDescription('Unable to generate description right now.');
    } finally {
      setIsNodeLoading(false);
    }
  }, []);

  const onEdgeClick = useCallback(async (_event: React.MouseEvent, edge: Edge) => {
    setSelectedNode(null);
    setNodeDescription('');
    setSelectedEdge(edge);
    setEdgeDescription('');
    const precomputedDescription =
      (edge as any)?.data?.llm_description ||
      (edge as any)?.data?.description;

    if (precomputedDescription) {
      setEdgeDescription(precomputedDescription);
      setIsEdgeLoading(false);
      return;
    }

    setIsEdgeLoading(true);

    try {
      const response = await codeArchitectureAPI.describeEdge({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: typeof edge.label === 'string' ? edge.label : undefined,
        relationshipType: (edge as any)?.data?.relationship_type || (edge as any)?.data?.type,
        protocol: typeof edge.label === 'string' ? edge.label : undefined,
      });
      setEdgeDescription(response?.description || 'No description available.');
    } catch (error) {
      setEdgeDescription('Unable to generate description right now.');
    } finally {
      setIsEdgeLoading(false);
    }
  }, []);

  const avgConnections =
    nodes.length > 0 ? (edges.length / nodes.length).toFixed(1) : '0';

  const toggleLevel = (level: string) => {
    setSelectedLevel(level);
  };

  const toggleRelationshipType = (type: string) => {
    setSelectedRelationshipTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  const systemAttributes =
    selectedNode?.type === 'system' ? selectedNode.attributes || {} : null;

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
          <p className="hint">
            Run extraction above or execute{' '}
            <code>python -m services.code_extraction.c4_extractor</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-architecture-viewer">
      <div className="viewer-header">
        <h2>Architecture Context (Multi-Repository)</h2>
        <p>
          Cumulative view of all added repositories - add multiple projects to
          see complete landscape
        </p>
      </div>

      <div className="viewer-layout">
        <aside className="filters-sidebar">
          <div className="filter-section">
            <h3>Extract Context</h3>

            {/* Single URL Quick Add */}
            <div className="quick-add-section">
              <input
                type="text"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onChange={e => setGithubUrl(e.target.value)}
                className="search-input"
                onKeyPress={e => e.key === 'Enter' && handleExtractFromGithub()}
              />
              <button
                className="fit-button"
                onClick={handleExtractFromGithub}
                disabled={isExtracting}
              >
                {isExtracting ? 'Extracting...' : 'Add Repository'}
              </button>
            </div>

            {/* Batch URL Input */}
            <div className="batch-section">
              <h4 className="subsection-title">Batch Input</h4>
              <BatchUrlInput
                onBatchExtract={handleBatchExtract}
                isExtracting={isExtracting}
              />
            </div>

            {/* GitHub Organization Scanner */}
            <div className="org-scan-section">
              <h4 className="subsection-title">GitHub Account/Org</h4>
              <GitHubOrgScanner
                onScanStart={handleGitHubOrgScan}
                isScanning={isExtracting}
              />
            </div>

            {/* Clear All Button */}
            <button
              className="reset-button"
              onClick={async () => {
                if (
                  confirm(
                    '⚠️ Clear ALL repositories and start fresh? This will remove all accumulated architecture data.'
                  )
                ) {
                  try {
                    await codeArchitectureAPI.clearArchitecture();
                    setArchitecture(null);
                    setNodes([]);
                    setEdges([]);
                    setGithubUrl('');
                    setExtractionStatus(
                      'All repositories cleared - ready for fresh extraction'
                    );
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

            {/* Status messages */}
            {extractionStatus && (
              <div className="extract-status">{extractionStatus}</div>
            )}
            {extractionError && (
              <div className="extract-error">{extractionError}</div>
            )}
            {architecture && (
              <div className="extract-info">
                <small>
                  💡 Data accumulates - add multiple repos to build complete
                  architecture view
                </small>
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
                <span>
                  {level
                    .replace('_', ' ')
                    .replace(/\b\w/g, l => l.toUpperCase())}
                </span>
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
                onEdgeClick={onEdgeClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                elementsSelectable
                edgesFocusable
                fitView
                attributionPosition="bottom-left"
                defaultViewport={{ x: 0, y: 0, zoom: 1.2 }}
                minZoom={0.05}
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
          )}
        </main>

        {selectedNode && (
          <aside className="node-details-panel">
            <div className="panel-header">
              <h3>{selectedNode.fullName || selectedNode.label}</h3>
              <button
                className="close-btn"
                onClick={() => setSelectedNode(null)}
              >
                ×
              </button>
            </div>
            <div className="panel-content">
              {nodeDescription && !isNodeLoading && (
                <div className="detail-row description-row">
                  <span className="detail-value description-text">
                    {normalizeDescription(nodeDescription)}
                  </span>
                </div>
              )}
              {isNodeLoading && (
                <div className="detail-row description-row">
                  <span className="detail-value description-text">Generating description…</span>
                </div>
              )}
              {!nodeDescription && !isNodeLoading && (systemAttributes?.purpose || selectedNode.containerMeta?.description || selectedNode.documentation) && (
                <div className="detail-row description-row">
                  <span className="detail-value description-text">
                    {systemAttributes?.purpose ||
                      selectedNode.containerMeta?.description ||
                      selectedNode.documentation ||
                      'No description available'}
                  </span>
                </div>
              )}

              {/* Domain field (from image: business bucket) */}
              {(systemAttributes?.business_domain ||
                systemAttributes?.domain ||
                selectedNode.attributes?.domain) && (
                <div className="detail-row">
                  <span className="detail-label">
                    domain
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Business area this service belongs to (e.g.
                        Infrastructure, AI/ML, Data, User Management).
                      </span>
                    </span>
                  </span>
                  <span className="detail-value">
                    {systemAttributes?.business_domain ||
                      systemAttributes?.domain ||
                      selectedNode.attributes?.domain}
                  </span>
                </div>
              )}

              {/* Owner field - always show when we have system/container context (even Unassigned) */}
              {(systemAttributes ||
                selectedNode.attributes?.owner != null ||
                selectedNode.attributes?.owner_contributors != null ||
                selectedNode.containerMeta?.owner) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Owner Team
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        The team or individual responsible for this system. If
                        unassigned, add a CODEOWNERS file or specify the team in
                        the README to assign ownership.
                      </span>
                    </span>
                  </span>
                  <span className="detail-value">
                    {systemAttributes?.owner_team ||
                      systemAttributes?.owner ||
                      selectedNode.containerMeta?.owner ||
                      selectedNode.attributes?.owner ||
                      'Unassigned'}
                  </span>
                  {(
                    (systemAttributes?.owner_contributors ||
                      selectedNode.attributes?.owner_contributors) ??
                    []
                  ).length > 0 && (
                    <div className="detail-sub">
                      Contributors:{' '}
                      {(
                        systemAttributes?.owner_contributors ||
                        selectedNode.attributes?.owner_contributors ||
                        []
                      )
                        .slice(0, 3)
                        .join(', ')}
                      {(
                        systemAttributes?.owner_contributors ||
                        selectedNode.attributes?.owner_contributors ||
                        []
                      ).length > 3 && '…'}
                    </div>
                  )}
                </div>
              )}

              {/* Status field (lifecycle: Active-Dev, Maintenance-Only, Deprecated) */}
              {(systemAttributes?.status ||
                selectedNode.attributes?.status) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Lifecycle Status
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Lifecycle stage: Active-Dev = new features being
                        developed. Maintenance-Only = bugfixes only, no new
                        features. Deprecated = scheduled for shutdown.
                      </span>
                    </span>
                  </span>
                  <span className="detail-value status-badge">
                    {systemAttributes?.status ||
                      selectedNode.attributes?.status}
                  </span>
                </div>
              )}

              {/* Tier field (criticality: Tier 1/2/3) */}
              {(systemAttributes?.criticality ||
                systemAttributes?.tier ||
                selectedNode.attributes?.tier) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Criticality Tier
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Tier 1 = Production Critical (site-wide outage if down).
                        Tier 2 = Standard (specific journey broken). Tier 3 =
                        Internal/Development (minor impact).
                      </span>
                    </span>
                  </span>
                  <span className="detail-value">
                    {systemAttributes?.criticality ||
                      systemAttributes?.tier ||
                      selectedNode.attributes?.tier}
                  </span>
                </div>
              )}

              {/* Data class field (sensitivity) */}
              {(systemAttributes?.data_class ||
                selectedNode.attributes?.data_class) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Data Sensitivity
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Personally Identifiable Information (PII) = names,
                        emails, addresses. Credit-Card = Payment data.
                        Legal/Security = Compliance, audit, encryption. General
                        = Non-sensitive data.
                      </span>
                    </span>
                  </span>
                  <span className="detail-value">
                    {systemAttributes?.data_class ||
                      selectedNode.attributes?.data_class}
                  </span>
                </div>
              )}

              {/* Active experts (bus factor) - warning when 0 */}
              {(systemAttributes?.active_experts != null ||
                selectedNode.attributes?.active_experts != null) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Active Experts (Bus Factor)
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Bus factor: contributors with 3+ commits in last 90
                        days. 0 = high risk (no active maintainers). 1 = single
                        point of failure. Higher is better.
                      </span>
                    </span>
                  </span>
                  <span
                    className={`detail-value active-experts-value ${
                      (systemAttributes?.active_experts ??
                        selectedNode.attributes?.active_experts ??
                        0) === 0
                        ? 'active-experts-zero'
                        : ''
                    }`}
                  >
                    {systemAttributes?.active_experts ??
                      selectedNode.attributes?.active_experts ??
                      0}
                  </span>
                </div>
              )}

              {/* Compliance (architectural risk) */}
              {(systemAttributes?.compliance ||
                selectedNode.attributes?.compliance) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Architectural Compliance
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        Architectural compliance status: COMPLIANT = well-owned,
                        appropriate tier. AT_RISK = sensitive data or no owner.
                        NON_COMPLIANT = critical gaps in governance.
                      </span>
                    </span>
                  </span>
                  <span className="detail-value status-badge">
                    {systemAttributes?.compliance ||
                      selectedNode.attributes?.compliance}
                  </span>
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
                  <span className="detail-value">
                    {selectedNode.containerMeta.technology}
                  </span>
                </div>
              )}

              {selectedNode.file && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">File:</span>
                  <span className="detail-value file-path">
                    {selectedNode.file}
                  </span>
                </div>
              )}

              {/* Show URL for external services */}
              {selectedNode.attributes?.url && (
                <div className="detail-row">
                  <span className="detail-label">Service URL</span>
                  <span className="detail-value">
                    <a
                      href={selectedNode.attributes.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="external-link"
                    >
                      {selectedNode.attributes.url}
                    </a>
                  </span>
                </div>
              )}

              {/* Show endpoint/access path for services */}
              {(selectedNode.containerMeta?.endpoint ||
                selectedNode.attributes?.endpoint ||
                selectedNode.attributes?.access_path) && (
                <div className="detail-row">
                  <span className="detail-label">
                    Access Endpoint
                    <span className="tooltip-hint">
                      ⓘ
                      <span className="tooltip-content">
                        The URL path or endpoint used to access this service or
                        UI directly. This could be an API endpoint, web
                        interface path, or service access URL.
                      </span>
                    </span>
                  </span>
                  <span className="detail-value">
                    <code className="endpoint-path">
                      {selectedNode.containerMeta?.endpoint ||
                        selectedNode.attributes?.endpoint ||
                        selectedNode.attributes?.access_path}
                    </code>
                  </span>
                </div>
              )}

              {selectedNode.attributes?.detected_from && (
                <div className="detail-row metadata-row">
                  <span className="detail-label">Detected from:</span>
                  <span className="detail-value">
                    {selectedNode.attributes.detected_from}
                  </span>
                </div>
              )}
            </div>
          </aside>
        )}

        {selectedEdge && (
          <aside className="node-details-panel">
            <div className="panel-header">
              <h3>{selectedEdge.label || 'Relationship'}</h3>
              <button className="close-btn" onClick={() => setSelectedEdge(null)}>×</button>
            </div>
            <div className="panel-content">
              <div className="detail-row description-row">
                <span className="detail-value description-text">
                  {isEdgeLoading ? 'Generating description…' : (edgeDescription || 'No description available')}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">from</span>
                <span className="detail-value">{selectedEdge.source}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">to</span>
                <span className="detail-value">{selectedEdge.target}</span>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
};

export default CodeArchitectureViewer;
