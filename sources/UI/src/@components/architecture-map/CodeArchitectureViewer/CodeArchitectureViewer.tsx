import React, {
  useEffect,
  useReducer,
  useCallback,
  useRef,
  useState,
} from "react";
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "dagre";
import axios from "axios";
import "./CodeArchitectureViewer.scss";
import type { ArchitectureChatMessage } from "../../../services/api";
import { codeArchitectureAPI } from "../../../services/api";
import CustomNode from "./CustomNode";
import ContainerNode from "./ContainerNode";
import C4Edge from "./C4Edge";
import ArchitectureHeader from "./components/ArchitectureHeader";
import GraphView from "./components/GraphView";
import NodeDetailsPanel from "./components/NodeDetailsPanel";
import EdgeDetailsPanel from "./components/EdgeDetailsPanel";
import MetricsBar from "./components/MetricsBar";
import { buildRenderedEdges } from "./edgeRendering";

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
}

interface DependencyReviewDecision {
  nodeId: string;
  value: string;
  label: string;
  description?: string;
}

const edgeTypes = {
  C4Edge,
};

export const generateC4Edges = (
  containers: any[] = [],
  relationships: any[] = [],
  contextExternalEntities: any[] = [],
): { nodes: Node[]; edges: Edge[] } => {
  const nameToId = new Map<string, string>();
  containers.forEach((container, idx) => {
    if (container?.name) {
      const id = `container_${container.name || idx}`;
      nameToId.set(container.name, id);
      // Store stripped form for helm name mismatch fallback
      if (container.name.startsWith("omnipay-")) {
        nameToId.set(container.name.slice(8), id);
      }
    }
  });

  // Build context external name → id lookup (normalise for matching)
  const contextExternalIdByName = new Map<string, string>();
  contextExternalEntities.forEach((ext) => {
    if (ext.name) {
      contextExternalIdByName.set(ext.name.toLowerCase(), ext.id);
      // Also store with spaces/dashes normalised
      const normalised = ext.name.toLowerCase().replace(/[-_\s]+/g, "");
      contextExternalIdByName.set(normalised, ext.id);
    }
  });

  const ghostNodes: Node[] = [];
  const ghostNodeIds = new Set<string>();
  const edges: Edge[] = [];
  const relationshipEdgesAdded = new Set<string>();

  const resolveId = (
    name: string,
  ): { id: string | null; isGhost: boolean } => {
    if (!name) return { id: null, isGhost: false };
    // 1. Direct container name lookup
    if (nameToId.has(name)) return { id: nameToId.get(name)!, isGhost: false };
    // 2. Strip omnipay- prefix and retry
    const stripped = name.startsWith("omnipay-") ? name.slice(8) : name;
    if (nameToId.has(stripped)) return { id: nameToId.get(stripped)!, isGhost: false };
    // 3. Check context externals (direct + normalised)
    const lowerName = name.toLowerCase();
    const normalised = lowerName.replace(/[-_\s]+/g, "");
    if (contextExternalIdByName.has(lowerName))
      return { id: contextExternalIdByName.get(lowerName)!, isGhost: false };
    if (contextExternalIdByName.has(normalised))
      return { id: contextExternalIdByName.get(normalised)!, isGhost: false };
    // 4. Create ghost external node (O(1) Set lookup)
    const ghostId = `ghost_external_${lowerName.replace(/[^a-z0-9]/g, "_")}`;
    if (!ghostNodeIds.has(ghostId)) {
      ghostNodeIds.add(ghostId);
      ghostNodes.push({
        id: ghostId,
        type: "custom",
        position: { x: 0, y: 0 },
        data: {
          label: name,
          type: "external_system",
          displayType: "External",
          isExternal: true,
          attributes: { isGhostExternal: true },
        },
      });
    }
    return { id: ghostId, isGhost: true };
  };

  relationships.forEach((rel, idx) => {
    const sourceName = rel?.from ?? rel?.source;
    const targetName = rel?.to ?? rel?.destination;
    if (!sourceName || !targetName) return;

    const sourceResult = resolveId(String(sourceName));
    const targetResult = resolveId(String(targetName));
    if (!sourceResult.id || !targetResult.id) return;

    const relationshipKey = `${sourceResult.id}-${targetResult.id}`;
    if (relationshipEdgesAdded.has(relationshipKey)) return;

    const protocol =
      typeof rel?.protocol === "string" ? rel.protocol.trim() : "";
    const label = protocol ? protocol.toUpperCase() : undefined;

    edges.push({
      id: `c4-rel-${sourceResult.id}-${targetResult.id}-${idx}`,
      source: sourceResult.id,
      target: targetResult.id,
      label,
      type: "C4Edge",
      interactionWidth: 16,
      markerEnd: { type: MarkerType.ArrowClosed },
      data: {
        description: rel?.description || rel?.llm_description,
        llm_description: rel?.llm_description,
        protocol: protocol || undefined,
        relationship_type: rel?.relationship_type || rel?.type,
      },
    });
    relationshipEdgesAdded.add(relationshipKey);
  });

  // Fallback: build edges from container.dependencies_internal when no relationships given
  if (relationships.length === 0) {
    containers.forEach((container, idx) => {
      const sourceId = `container_${container.name || idx}`;
      const protocol =
        typeof container?.protocol === "string" ? container.protocol.trim() : "";
      const label = protocol ? protocol.toUpperCase() : undefined;
      const deps: string[] = Array.isArray(container?.dependencies_internal)
        ? container.dependencies_internal.map(String)
        : [];

      deps.forEach((depName, depIdx) => {
        const targetResult = resolveId(depName);
        if (!targetResult.id) return;
        const key = `${sourceId}-${targetResult.id}`;
        if (relationshipEdgesAdded.has(key)) return;

        edges.push({
          id: `c4-rel-${sourceId}-${targetResult.id}-${depIdx}`,
          source: sourceId,
          target: targetResult.id,
          label,
          type: "C4Edge",
          interactionWidth: 16,
          markerEnd: { type: MarkerType.ArrowClosed },
          data: { protocol, relationship_type: "uses" },
        });
        relationshipEdgesAdded.add(key);
      });
    });
  }

  return { nodes: ghostNodes, edges };
};

const normalizeDescription = (text?: string) => {
  if (!text) return "";
  return text.replace(/\s+/g, " ").trim();
};

const nodeTypes = {
  custom: CustomNode,
  container: ContainerNode,
};

// Layout function - grid layout for components in containers
const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = "LR",
) => {
  if (nodes.length === 0) {
    return { nodes: [], edges };
  }

  // Separate parent containers and child nodes
  const containerNodes = nodes.filter((n) => n.type === "container");
  const childNodes = nodes.filter((n) => n.parentNode);
  const standaloneNodes = nodes.filter(
    (n) => !n.type?.includes("container") && !n.parentNode,
  );

  // Layout child nodes within their parent containers
  if (containerNodes.length > 0) {
    // Position containers with MUCH more spacing
    const containerSpacing = 180;
    let currentX = 200;

    const childNodeWidth = 240;
    const childNodeHeight = 120;
    const childSpacing = 50;
    const childStartX = 60;
    const childStartY = 100;

    containerNodes.forEach((container) => {
      container.position = { x: currentX, y: 150 };

      // Get children of this container
      const children = childNodes.filter((n) => n.parentNode === container.id);

      // Layout children in a grid inside the container (more horizontal when possible)
      const minColumns = 2;
      const maxColumns = 4;
      const childrenPerRow = Math.min(
        maxColumns,
        Math.max(minColumns, Math.ceil(children.length / 2)),
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
          width: Math.max(800, contentWidth),
          height: Math.max(520, contentHeight),
        };
      }

      currentX +=
        ((container.style?.width as number) || 850) + containerSpacing;
    });

    // Position standalone nodes (non-K8s containers, non-child entities)
    // below the cluster frame in a grid layout
    if (standaloneNodes.length > 0) {
      // Find the bottom edge of positioned containers
      let maxY = 0;
      containerNodes.forEach((c) => {
        const h = (c.style?.height as number) || 520;
        maxY = Math.max(maxY, (c.position?.y || 0) + h);
      });

      const standaloneStartY = maxY + 80;
      const cols = Math.min(
        5,
        Math.max(2, Math.ceil(Math.sqrt(standaloneNodes.length))),
      );
      const nodeW = 260;
      const nodeH = 120;
      const gapX = 40;
      const gapY = 40;

      standaloneNodes.forEach((node, idx) => {
        const row = Math.floor(idx / cols);
        const col = idx % cols;
        node.position = {
          x: 200 + col * (nodeW + gapX),
          y: standaloneStartY + row * (nodeH + gapY),
        };
        node.sourcePosition = Position.Right;
        node.targetPosition = Position.Left;
      });
    }

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
    nodes.forEach((node) => {
      const method =
        node.data.type === "component"
          ? node.data.fullName?.split(" ")[0] || "OTHER"
          : "OTHER";

      if (!methodGroups.has(method)) {
        methodGroups.set(method, []);
      }
      methodGroups.get(method)!.push(node);
    });

    // Layout in columns by method
    const methodOrder = ["GET", "POST", "PUT", "PATCH", "DELETE", "OTHER"];
    let columnX = 100;
    const columnWidth = 280;
    const rowHeight = 150;

    const layoutedNodes = nodes.map((node) => {
      const method =
        node.data.type === "component"
          ? node.data.fullName?.split(" ")[0] || "OTHER"
          : "OTHER";

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

    // Enhanced dagre config - MUCH larger spacing to prevent overlapping
    dagreGraph.setGraph({
      rankdir: direction,
      align: "UL",
      ranksep: 240, // More room for context labels and edge curves
      nodesep: 155, // Keep neighboring nodes from pinching labels
      edgesep: 70, // Give parallel edges enough breathing room
      marginx: 150, // Larger margins
      marginy: 150, // Larger margins
      ranker: "network-simplex",
    });

    // Increased node dimensions to match the visual size
    nodes.forEach((node) => {
      dagreGraph.setNode(node.id, {
        width: 240,
        height: 130,
      });
    });

    edges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
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

  // If no edges, use an improved grid layout with much better spacing
  const nodesPerRow = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  const nodeWidth = 260;
  const nodeHeight = 140;
  const spacingX = 140; // Major increase
  const spacingY = 120; // Major increase

  const layoutedNodes = nodes.map((node, index) => {
    const row = Math.floor(index / nodesPerRow);
    const col = index % nodesPerRow;

    return {
      ...node,
      position: {
        x: col * (nodeWidth + spacingX) + 180,
        y: row * (nodeHeight + spacingY) + 180,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  return { nodes: layoutedNodes, edges };
};

// Improved layout for C4 Context level: users/persons left, system center, externals right
function layoutContextLevel(nodes: Node[]): Node[] {
  // Center of the canvas
  const cx = 800;
  const cy = 450;

  // Categorize nodes
  const system = nodes.find((n) => n.data?.type === "system");
  const persons = nodes.filter((n) => n.data?.type === "person");
  const externals = nodes.filter(
    (n) =>
      n.data?.type !== "system" &&
      n.data?.type !== "person" &&
      n.data?.is_external,
  );
  const otherExternals = nodes.filter(
    (n) =>
      n.data?.type !== "system" &&
      n.data?.type !== "person" &&
      !n.data?.is_external,
  );

  // Node dimensions for spacing calculations
  const nodeWidth = 260;
  const nodeHeight = 140;
  const personsX = 80; // Far left
  const externalsX = cx + 400; // Far right
  const systemX = cx - nodeWidth / 2; // Center
  const systemY = cy - nodeHeight / 2;

  // Place system in the center
  if (system) {
    system.position = { x: systemX, y: systemY };
    system.sourcePosition = Position.Right;
    system.targetPosition = Position.Left;
  }

  // Place persons/users on the LEFT side - stacked vertically with good spacing
  const personSpacingY = 180;
  persons.forEach((n, i) => {
    n.position = {
      x: personsX,
      y: cy - ((persons.length - 1) * personSpacingY) / 2 + i * personSpacingY,
    };
    n.sourcePosition = Position.Right;
    n.targetPosition = Position.Left;
  });

  // Place external systems on the RIGHT side - stacked vertically
  const allExternals = [...externals, ...otherExternals];
  const externalSpacingY = 180;
  allExternals.forEach((n, i) => {
    n.position = {
      x: externalsX,
      y:
        cy -
        ((allExternals.length - 1) * externalSpacingY) / 2 +
        i * externalSpacingY,
    };
    n.sourcePosition = Position.Left;
    n.targetPosition = Position.Right;
  });

  return nodes;
}

const CodeArchitectureViewer: React.FC = () => {
  return (
    <ReactFlowProvider>
      <CodeArchitectureViewerInner />
    </ReactFlowProvider>
  );
};

// ── State types & reducers ────────────────────────────────────────────────────

interface ArchState {
  architecture: C4Architecture | null;
  loading: boolean;
  error: string | null;
}
type ArchAction =
  | { type: "SET_ARCHITECTURE"; payload: C4Architecture | null }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_ERROR"; payload: string | null };

function archReducer(state: ArchState, action: ArchAction): ArchState {
  switch (action.type) {
    case "SET_ARCHITECTURE":
      return { ...state, architecture: action.payload };
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    default:
      return state;
  }
}

interface FilterState {
  selectedLevel: string;
  selectedEntityTypes: string[];
  selectedRelationshipTypes: string[];
  showExternal: boolean;
  dependencyViewFilter: "all" | "business" | "technical";
  searchTerm: string;
  relationshipTypes: string[];
}
type FilterAction =
  | { type: "SET_LEVEL"; payload: string }
  | { type: "SET_ENTITY_TYPES"; payload: string[] }
  | { type: "SET_RELATIONSHIP_TYPES"; payload: string[] }
  | { type: "SET_SHOW_EXTERNAL"; payload: boolean }
  | { type: "SET_DEPENDENCY_VIEW"; payload: "all" | "business" | "technical" }
  | { type: "SET_SEARCH_TERM"; payload: string }
  | { type: "SET_REL_TYPE_LIST"; payload: string[] };

function filterReducer(state: FilterState, action: FilterAction): FilterState {
  switch (action.type) {
    case "SET_LEVEL":
      return { ...state, selectedLevel: action.payload };
    case "SET_ENTITY_TYPES":
      return { ...state, selectedEntityTypes: action.payload };
    case "SET_RELATIONSHIP_TYPES":
      return { ...state, selectedRelationshipTypes: action.payload };
    case "SET_SHOW_EXTERNAL":
      return { ...state, showExternal: action.payload };
    case "SET_DEPENDENCY_VIEW":
      return { ...state, dependencyViewFilter: action.payload };
    case "SET_SEARCH_TERM":
      return { ...state, searchTerm: action.payload };
    case "SET_REL_TYPE_LIST":
      return { ...state, relationshipTypes: action.payload };
    default:
      return state;
  }
}

interface SelectionState {
  selectedNode: any;
  selectedEdge: any;
  nodeDescription: string;
  edgeDescription: string;
  isNodeLoading: boolean;
  isEdgeLoading: boolean;
}
type SelectionAction =
  | { type: "SELECT_NODE"; node: any; description: string }
  | { type: "SET_NODE_DESCRIPTION"; payload: string }
  | { type: "CLEAR_NODE" }
  | { type: "SELECT_EDGE"; edge: any }
  | { type: "SET_EDGE_DESCRIPTION"; payload: string }
  | { type: "SET_EDGE_LOADING"; payload: boolean }
  | { type: "CLEAR_EDGE" };

function selectionReducer(
  state: SelectionState,
  action: SelectionAction,
): SelectionState {
  switch (action.type) {
    case "SELECT_NODE":
      return {
        ...state,
        selectedNode: action.node,
        nodeDescription: action.description,
        isNodeLoading: false,
        selectedEdge: null,
        edgeDescription: "",
      };
    case "SET_NODE_DESCRIPTION":
      return {
        ...state,
        nodeDescription: action.payload,
        isNodeLoading: false,
      };
    case "CLEAR_NODE":
      return {
        ...state,
        selectedNode: null,
        nodeDescription: "",
        isNodeLoading: false,
      };
    case "SELECT_EDGE":
      return {
        ...state,
        selectedEdge: action.edge,
        edgeDescription: "",
        isEdgeLoading: false,
        selectedNode: null,
        nodeDescription: "",
      };
    case "SET_EDGE_DESCRIPTION":
      return {
        ...state,
        edgeDescription: action.payload,
        isEdgeLoading: false,
      };
    case "SET_EDGE_LOADING":
      return { ...state, isEdgeLoading: action.payload };
    case "CLEAR_EDGE":
      return {
        ...state,
        selectedEdge: null,
        edgeDescription: "",
        isEdgeLoading: false,
      };
    default:
      return state;
  }
}

interface ExtractionState {
  githubUrl: string;
  localPath: string;
  isExtracting: boolean;
  extractionStatus: string | null;
  extractionError: string | null;
  repoSectionExpanded: boolean;
}
type ExtractionAction =
  | { type: "SET_URL"; payload: string }
  | { type: "SET_LOCAL_PATH"; payload: string }
  | { type: "SET_EXTRACTING"; payload: boolean }
  | { type: "SET_STATUS"; payload: string | null }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "TOGGLE_REPO_SECTION" }
  | { type: "SET_REPO_EXPANDED"; payload: boolean };

function extractionReducer(
  state: ExtractionState,
  action: ExtractionAction,
): ExtractionState {
  switch (action.type) {
    case "SET_URL":
      return { ...state, githubUrl: action.payload };
    case "SET_LOCAL_PATH":
      return { ...state, localPath: action.payload };
    case "SET_EXTRACTING":
      return { ...state, isExtracting: action.payload };
    case "SET_STATUS":
      return { ...state, extractionStatus: action.payload };
    case "SET_ERROR":
      return { ...state, extractionError: action.payload };
    case "TOGGLE_REPO_SECTION":
      return { ...state, repoSectionExpanded: !state.repoSectionExpanded };
    case "SET_REPO_EXPANDED":
      return { ...state, repoSectionExpanded: action.payload };
    default:
      return state;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

const CodeArchitectureViewerInner: React.FC = () => {
  const [archState, archDispatch] = useReducer(archReducer, {
    architecture: null,
    loading: true,
    error: null,
  });
  const { architecture, loading, error } = archState;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();

  const [filterState, filterDispatch] = useReducer(filterReducer, {
    selectedLevel: "context_level",
    selectedEntityTypes: [],
    selectedRelationshipTypes: [],
    showExternal: true,
    dependencyViewFilter: "business",
    searchTerm: "",
    relationshipTypes: [],
  });
  const {
    selectedLevel,
    selectedEntityTypes,
    selectedRelationshipTypes,
    showExternal,
    dependencyViewFilter,
    searchTerm,
    relationshipTypes,
  } = filterState;

  const [selState, selDispatch] = useReducer(selectionReducer, {
    selectedNode: null,
    selectedEdge: null,
    nodeDescription: "",
    edgeDescription: "",
    isNodeLoading: false,
    isEdgeLoading: false,
  });
  const {
    selectedNode,
    selectedEdge,
    nodeDescription,
    edgeDescription,
    isNodeLoading,
    isEdgeLoading,
  } = selState;
  const [chatMessages, setChatMessages] = useState<ArchitectureChatMessage[]>(
    [],
  );
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [reviewOverrides, setReviewOverrides] = useState<
    Record<string, Record<string, unknown>>
  >({});

  const [exState, exDispatch] = useReducer(extractionReducer, {
    githubUrl: "",
    isExtracting: false,
    extractionStatus: null,
    extractionError: null,
    repoSectionExpanded: true,
    localPath: "",
  });
  const {
    githubUrl,
    localPath,
    isExtracting,
    extractionStatus,
    extractionError,
    repoSectionExpanded,
  } = exState;

  const pollIntervalRef = useRef<number | null>(null);

  // ── Shim setters (keep child prop interfaces unchanged) ───────────────────
  const setArchitecture = (v: C4Architecture | null) =>
    archDispatch({ type: "SET_ARCHITECTURE", payload: v });
  const setLoading = (v: boolean) =>
    archDispatch({ type: "SET_LOADING", payload: v });
  const setError = (v: string | null) =>
    archDispatch({ type: "SET_ERROR", payload: v });

  const setSelectedLevel = (v: string) =>
    filterDispatch({ type: "SET_LEVEL", payload: v });
  const setSelectedEntityTypes = (v: string[]) =>
    filterDispatch({ type: "SET_ENTITY_TYPES", payload: v });
  const setSelectedRelationshipTypes = (v: string[]) =>
    filterDispatch({ type: "SET_RELATIONSHIP_TYPES", payload: v });
  const setShowExternal = (v: boolean) =>
    filterDispatch({ type: "SET_SHOW_EXTERNAL", payload: v });
  const setDependencyViewFilter = (v: "all" | "business" | "technical") =>
    filterDispatch({ type: "SET_DEPENDENCY_VIEW", payload: v });
  const setSearchTerm = (v: string) =>
    filterDispatch({ type: "SET_SEARCH_TERM", payload: v });
  const setRelationshipTypes = (v: string[]) =>
    filterDispatch({ type: "SET_REL_TYPE_LIST", payload: v });

  const setSelectedNode = (node: any) => {
    if (node === null) {
      selDispatch({ type: "CLEAR_NODE" });
    } else {
      selDispatch({ type: "SELECT_NODE", node, description: "" });
    }
  };
  const setSelectedEdge = (edge: any) => {
    if (edge === null) {
      selDispatch({ type: "CLEAR_EDGE" });
    } else {
      selDispatch({ type: "SELECT_EDGE", edge });
    }
  };
  const setNodeDescription = (v: string) =>
    selDispatch({ type: "SET_NODE_DESCRIPTION", payload: v });
  const setEdgeDescription = (v: string) =>
    selDispatch({ type: "SET_EDGE_DESCRIPTION", payload: v });
  const setIsNodeLoading = (_v: boolean) => {
    /* handled by SELECT_NODE/CLEAR_NODE */
  };
  const setIsEdgeLoading = (v: boolean) =>
    selDispatch({ type: "SET_EDGE_LOADING", payload: v });

  const setGithubUrl = (v: string) =>
    exDispatch({ type: "SET_URL", payload: v });
  const setLocalPath = (v: string) =>
    exDispatch({ type: "SET_LOCAL_PATH", payload: v });
  const setIsExtracting = (v: boolean) =>
    exDispatch({ type: "SET_EXTRACTING", payload: v });
  const setExtractionStatus = (v: string | null) =>
    exDispatch({ type: "SET_STATUS", payload: v });
  const setExtractionError = (v: string | null) =>
    exDispatch({ type: "SET_ERROR", payload: v });
  const setRepoSectionExpanded = (v: boolean) =>
    exDispatch({ type: "SET_REPO_EXPANDED", payload: v });

  const applyArchitecture = useCallback((data: any) => {
    // Ensure c4_model_version exists (API might not include it)
    if (!data.c4_model_version) {
      data.c4_model_version = "1.0";
    }

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
        compliance_confidence: sysCtx.compliance_confidence,
        compliance_factors: sysCtx.compliance_factors,
      };
      const containerEntities: CodeEntity[] = data.containers.map(
        (container: any, idx: number) => ({
          id: `container_${container.name || idx}`,
          name: container.name,
          entity_type: "container",
          language: container.technology || "Unknown",
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
        }),
      );

      // Create relationships from containers
      const containerRelationships: CodeRelationship[] = [];

      // Merge container-level relationships from C4 JSON
      if (data.relationships?.containers?.length) {
        const containerIdByName = new Map(
          containerEntities.map((c) => [c.name, c.id]),
        );

        data.relationships.containers.forEach(
          (rel: C4DiagramRelationship, idx: number) => {
            const sourceName = (rel as any).from ?? rel.source;
            const targetName = (rel as any).to ?? rel.destination;
            const sourceId = sourceName
              ? containerIdByName.get(String(sourceName))
              : undefined;
            const targetId = targetName
              ? containerIdByName.get(String(targetName))
              : undefined;

            if (sourceId && targetId) {
              containerRelationships.push({
                id: `rel_container_${idx}`,
                source_entity_id: sourceId,
                target_entity_id: targetId,
                relationship_type:
                  rel.relationship_type || (rel as any).type || "depends_on",
                attributes: {
                  description: rel.description || (rel as any).llm_description,
                  protocol: (rel as any).protocol,
                },
              });
            }
          },
        );
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

      const systemName = data.system_context?.name || "System";
      const systemId = `context_system_${systemName}`;

      contextEntities.push({
        id: systemId,
        name: systemName,
        entity_type: "system",
        language: "Unknown",
        file_path: "",
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
          compliance_confidence: data.system_context?.compliance_confidence,
          compliance_factors: data.system_context?.compliance_factors,
          purpose:
            data.system_context?.purpose || data.system_context?.description,
          description:
            data.system_context?.description || data.system_context?.purpose,
          languages: data.system_context?.languages,
          frameworks: data.system_context?.frameworks,
          repository_url: data.system_context?.repository_url,
          git: data.system_context?.git,
          context_sources: data.system_context?.context_sources,
          external_dependencies: data.system_context?.external_dependencies,
          documentation_quality: data.system_context?.documentation_quality,
          deployment_targets: data.system_context?.deployment_targets,
          dora_metrics: data.system_context?.dora_metrics,
          last_commit_date: data.system_context?.last_commit_date,
          commit_count_30d: data.system_context?.commit_count_30d,
          commit_count_90d: data.system_context?.commit_count_90d,
          // Derived: count containers as service_count
          service_count: (data.containers || []).length || undefined,
          // Actors list for panel display
          actors: data.system_context?.actors,
        },
      });

      const actorEntities = (data.system_context?.actors || []).map(
        (actor: any, idx: number) => ({
          id: `context_actor_${idx}`,
          name: actor.name || `Actor ${idx + 1}`,
          entity_type: actor.type || "person",
          language: "Unknown",
          file_path: "",
          attributes: {
            description: actor.description || actor.role || "",
            role: actor.role || actor.type || "person",
            detected_from: actor.detected_from,
            detection_method: actor.detection_method,
            evidence: actor.evidence,
          },
        }),
      );

      // Types that map to TECHNICAL_INFRA when dependency_type is not set
      const TECH_INFRA_DEP_TYPES = new Set([
        "database",
        "cache",
        "logging",
        "documentation",
        "queue",
      ]);
      const inferDepType = (
        dep: any,
      ): { dep_type: string; dep_confidence: number } => {
        if (dep.dependency_type && dep.dependency_type !== "UNKNOWN") {
          return {
            dep_type: dep.dependency_type,
            dep_confidence: dep.classification_confidence ?? 0.5,
          };
        }
        if (TECH_INFRA_DEP_TYPES.has(dep.type)) {
          return { dep_type: "TECHNICAL_INFRA", dep_confidence: 0.85 };
        }
        if (dep.type === "external_service" || dep.type === "external_system") {
          return { dep_type: "BUSINESS_SYSTEM", dep_confidence: 0.6 };
        }
        return { dep_type: "UNKNOWN", dep_confidence: 0.5 };
      };

      const externalEntities = (
        data.system_context?.external_dependencies || []
      ).map((dep: any, idx: number) => {
        const { dep_type, dep_confidence } = inferDepType(dep);
        return {
          id: `context_external_${idx}`,
          name:
            dep.context_name ||
            dep.company ||
            dep.provider ||
            dep.name ||
            dep.url ||
            `External ${idx + 1}`,
          entity_type: dep.type || "external_system",
          language: "Unknown",
          file_path: dep.detected_from || "",
          attributes: {
            raw_name: dep.name,
            context_name: dep.context_name,
            provider: dep.provider,
            company: dep.company,
            url: dep.url,
            detected_from: dep.detected_from,
            is_external: true,
            protocol: dep.protocol,
            integration_surface: dep.integration_surface,
            dependency_type: dep_type,
            classification_confidence: dep_confidence,
            classification_reasoning: dep.classification_reasoning || "",
            decision_mode: dep.decision_mode || dep.decision?.decision_mode,
            review_status: dep.review_status || dep.decision?.review_status,
            requires_human_review:
              dep.requires_human_review || dep.review_status === "needs_review",
            review_threshold: dep.review_threshold,
            review_item: dep.review_item,
            review_options: dep.review_options,
            suggested_prompts: dep.suggested_prompts,
            provider_alternatives: dep.provider_alternatives,
            evidence: dep.evidence,
          },
        };
      });

      contextEntities.push(...actorEntities, ...externalEntities);

      const contextIdByName = new Map<string, string>();
      contextEntities.forEach((entity) => {
        contextIdByName.set(entity.name, entity.id);
      });
      externalEntities.forEach((entity, idx) => {
        const rawDependency = data.system_context?.external_dependencies?.[idx];
        if (rawDependency?.name) {
          contextIdByName.set(String(rawDependency.name), entity.id);
        }
        if (rawDependency?.context_name) {
          contextIdByName.set(String(rawDependency.context_name), entity.id);
        }
      });

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
                relationship_type: rel.relationship_type || "uses",
                attributes: {
                  description: rel.description,
                },
              });
            }
          },
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
        compliance_confidence: sysCtxForComponents.compliance_confidence,
        compliance_factors: sysCtxForComponents.compliance_factors,
      };
      data.components.forEach((component: any, groupIdx: number) => {
        // Check if this is a component group
        if (
          component.type === "component_group" &&
          component.components &&
          Array.isArray(component.components)
        ) {
          // Expand the grouped components
          component.components.forEach((compName: string, idx: number) => {
            const compId = `component_${groupIdx}_${idx}`;
            componentEntities.push({
              id: compId,
              name: compName,
              entity_type: "component",
              language: "Unknown",
              file_path: component.name, // Use group name as path/module
              attributes: {
                component_type: component.component_type || "Component",
                group: component.name,
                container: component.container,
                ...inheritedForComponents,
              },
            });

            // Create relationship to container
            if (component.container && data.container_level?.entities) {
              const containerEntity = data.container_level.entities.find(
                (c: CodeEntity) => c.name === component.container,
              );
              if (containerEntity) {
                componentRelationships.push({
                  id: `rel_comp_${compId}_${containerEntity.id}`,
                  source_entity_id: containerEntity.id,
                  target_entity_id: compId,
                  relationship_type: "contains",
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
            entity_type: "component",
            language: component.technology || "Unknown",
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
              (c: CodeEntity) => c.name === component.container,
            );
            if (containerEntity) {
              componentRelationships.push({
                id: `rel_comp_${compId}_${containerEntity.id}`,
                source_entity_id: containerEntity.id,
                target_entity_id: compId,
                relationship_type: "contains",
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

    // Extract unique entity and relationship types
    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];
    const levelsForFilters = [
      "context_level",
      "container_level",
      "component_level",
    ];

    levelsForFilters.forEach((level) => {
      if (data[level as keyof C4Architecture]) {
        const levelData = data[level as keyof C4Architecture] as C4Level;
        if (levelData.entities) allEntities.push(...levelData.entities);
        if (levelData.relationships)
          allRelationships.push(...levelData.relationships);
      }
    });

    const uniqueEntityTypes = Array.from(
      new Set(allEntities.map((e) => e.entity_type)),
    );
    const uniqueRelTypes = Array.from(
      new Set(allRelationships.map((r) => r.relationship_type)),
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
          err instanceof Error ? err.message : "Failed to load architecture",
        );
      } finally {
        setLoading(false);
      }
    };

    loadArchitecture();
  }, [applyArchitecture]);

  useEffect(() => {
    setChatMessages([]);
    setIsChatLoading(false);
  }, [selectedNode, selectedEdge]);

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
      setExtractionError("Please enter a GitHub URL");
      return;
    }

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setExtractionError(null);
    setExtractionStatus("Starting extraction...");
    setIsExtracting(true);

    try {
      const response = await codeArchitectureAPI.extractFromGitHub(
        githubUrl.trim(),
        true,
      );
      const taskId = response.task_id;

      if (!taskId) {
        throw new Error("No task id returned from extraction");
      }

      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const status = await codeArchitectureAPI.getExtractionStatus(taskId);
          const progress =
            typeof status.progress === "number"
              ? Math.round(status.progress * 100)
              : null;
          const statusLabel = status.message || status.status;
          setExtractionStatus(
            progress !== null ? `${statusLabel} (${progress}%)` : statusLabel,
          );

          if (status.status === "completed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionStatus("Extraction completed");

            const results =
              await codeArchitectureAPI.getExtractionResults(taskId);
            if (results) {
              applyArchitecture(results);
              setSelectedLevel("context_level");
            }
          } else if (status.status === "failed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionError(status.message || "Extraction failed");
          }
        } catch (pollError) {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsExtracting(false);
          setExtractionError("Failed to poll extraction status");
        }
      }, 2000);
    } catch (err) {
      setIsExtracting(false);
      setExtractionError(
        err instanceof Error ? err.message : "Failed to start extraction",
      );
    }
  }, [githubUrl, applyArchitecture]);

  // Local folder scan handler
  const handleScanLocalPath = useCallback(async () => {
    const path = localPath.trim();
    if (!path) {
      setExtractionError("Please enter a local folder path (e.g. /cms)");
      return;
    }

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setExtractionError(null);
    setExtractionStatus(`Scanning ${path}...`);
    setIsExtracting(true);

    try {
      const response = await codeArchitectureAPI.scanLocalPath(path);
      const taskId = response.task_id;

      if (!taskId) {
        throw new Error("No task id returned from scan");
      }

      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const status = await codeArchitectureAPI.getExtractionStatus(taskId);
          const progress =
            typeof status.progress === "number"
              ? Math.round(status.progress * 100)
              : null;
          const statusLabel = status.message || status.status;
          setExtractionStatus(
            progress !== null ? `${statusLabel} (${progress}%)` : statusLabel,
          );

          if (status.status === "completed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionStatus("Scan completed");

            const results =
              await codeArchitectureAPI.getExtractionResults(taskId);
            if (results) {
              applyArchitecture(results);
              setSelectedLevel("context_level");
            }
          } else if (status.status === "failed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionError(status.message || "Scan failed");
          }
        } catch {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsExtracting(false);
          setExtractionError("Failed to poll scan status");
        }
      }, 2000);
    } catch (err) {
      setIsExtracting(false);
      setExtractionError(
        err instanceof Error ? err.message : "Failed to start scan",
      );
    }
  }, [localPath, applyArchitecture]);

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
          `Extracting ${i + 1}/${urls.length}: ${url.replace("https://github.com/", "")}`,
        );

        try {
          const response = await codeArchitectureAPI.extractFromGitHub(
            url,
            true,
            true,
          );
          const taskId = response.task_id;

          // Poll for completion
          let completed = false;
          while (!completed) {
            await new Promise((resolve) => setTimeout(resolve, 2000));
            const status =
              await codeArchitectureAPI.getExtractionStatus(taskId);

            const progress =
              typeof status.progress === "number"
                ? Math.round(status.progress * 100)
                : null;

            setExtractionStatus(
              `Extracting ${i + 1}/${urls.length}: ${url.replace("https://github.com/", "")} ${progress !== null ? `(${progress}%)` : ""}`,
            );

            if (status.status === "completed") {
              completed = true;
            } else if (status.status === "failed") {
              throw new Error(status.message || "Extraction failed");
            }
          }
        } catch (err) {
          console.error(`Failed on ${url}:`, err);
          setExtractionError(
            `Failed on ${url}: ${err instanceof Error ? err.message : "Unknown error"}`,
          );
          // Continue with remaining URLs
        }
      }

      setIsExtracting(false);
      setExtractionStatus(
        `Batch extraction completed - ${urls.length} repositories analyzed`,
      );

      // Reload architecture data
      try {
        const data = await codeArchitectureAPI.getArchitecture();
        applyArchitecture(data);
        setSelectedLevel("context_level");
      } catch (err) {
        console.error("Failed to reload architecture:", err);
      }
    },
    [applyArchitecture],
  );

  // GitHub organization scan handler
  const handleGitHubOrgScan = useCallback(
    async (
      username: string,
      options: { includeForks: boolean; maxRepos: number },
    ) => {
      setIsExtracting(true);
      setExtractionError(null);
      setExtractionStatus(`Scanning ${username} for repositories...`);

      try {
        const response = await codeArchitectureAPI.extractFromGitHubOrg(
          username,
          options.includeForks,
          options.maxRepos,
          true, // append_mode
        );

        const taskId = response.task_id;

        // Poll for batch completion
        const pollInterval = setInterval(async () => {
          try {
            const status =
              await codeArchitectureAPI.getExtractionStatus(taskId);

            const progress =
              typeof status.progress === "number"
                ? Math.round(status.progress * 100)
                : null;

            const completed = (status as any).completed_repos || 0;
            const total = (status as any).total_repos || options.maxRepos;

            setExtractionStatus(
              `Extracting ${completed}/${total} repositories... ${progress !== null ? `(${progress}%)` : ""}`,
            );

            if (status.status === "completed") {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionStatus(
                `GitHub org scan completed - ${total} repositories analyzed`,
              );

              // Reload architecture
              const data = await codeArchitectureAPI.getArchitecture();
              applyArchitecture(data);
              setSelectedLevel("context_level");
            } else if (status.status === "failed") {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionError(status.message || "GitHub org scan failed");
            }
          } catch (pollError) {
            clearInterval(pollInterval);
            setIsExtracting(false);
            setExtractionError("Failed to poll extraction status");
          }
        }, 3000); // Poll every 3 seconds for batch operations
      } catch (err) {
        setIsExtracting(false);
        let errorMessage = "Failed to scan GitHub organization";

        if (axios.isAxiosError(err)) {
          if (err.response) {
            // Server responded with error
            const status = err.response.status;
            const detail = err.response.data?.detail || err.message;

            if (status === 404) {
              errorMessage = `GitHub user/org '${username}' not found`;
            } else if (status === 429) {
              errorMessage = detail; // Rate limit message from backend
            } else if (status === 403) {
              errorMessage = `Access denied to '${username}'. Repository may be private.`;
            } else if (status === 504) {
              errorMessage =
                "Request timed out. Try reducing max repositories or try again.";
            } else {
              errorMessage = detail || `Server error (${status})`;
            }
          } else if (err.code === "ECONNABORTED") {
            errorMessage =
              "Request timed out. GitHub API may be slow. Try again with fewer repositories.";
          } else if (err.message) {
            errorMessage = err.message;
          }
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }

        setExtractionError(errorMessage);
      }
    },
    [applyArchitecture],
  );

  // Process architecture data into graph format
  useEffect(() => {
    if (!architecture) {
      return;
    }

    const allEntities: CodeEntity[] = [];
    const allRelationships: CodeRelationship[] = [];

    // Collect entities and relationships from the selected level
    if (architecture[selectedLevel as keyof C4Architecture]) {
      const levelData = architecture[
        selectedLevel as keyof C4Architecture
      ] as C4Level;
      if (levelData.entities) {
        // Add level metadata to each entity
        allEntities.push(
          ...levelData.entities.map((e) => ({ ...e, level: selectedLevel })),
        );
      }
      if (levelData.relationships) {
        allRelationships.push(...levelData.relationships);
      }
    }

    // Fallback: build minimal level data if the backend didn't provide it
    if (
      allEntities.length === 0 &&
      selectedLevel === "container_level" &&
      architecture.containers?.length
    ) {
      const fallbackContainers = architecture.containers.map(
        (container: any, idx: number) => ({
          id: `container_${container.name || idx}`,
          name: container.name,
          entity_type: "container",
          language: container.technology || "Unknown",
          file_path: container.path,
          attributes: {
            container_type: container.container_type,
            protocol: container.protocol,
            runtime_info: container.runtime_info,
            runtime_environment: container.runtime_environment,
            deployment: container.deployment,
          },
          level: selectedLevel,
        }),
      );
      allEntities.push(...fallbackContainers);
    }

    if (
      allEntities.length === 0 &&
      selectedLevel === "context_level" &&
      architecture.system_context
    ) {
      const sc = architecture.system_context;
      const systemName = sc?.name || "System";
      allEntities.push({
        id: `context_system_${systemName}`,
        name: systemName,
        entity_type: "system",
        language: "Unknown",
        file_path: "",
        attributes: {
          owner_team: sc?.owner_team,
          owner: sc?.owner,
          owner_contributors: sc?.owner_contributors,
          owner_contributor_stats: sc?.owner_contributor_stats,
          business_domain: sc?.business_domain,
          domain: sc?.domain,
          criticality: sc?.criticality,
          tier: sc?.tier,
          status: sc?.status,
          data_class: sc?.data_class,
          active_experts: sc?.active_experts,
          compliance: sc?.compliance,
          compliance_confidence: sc?.compliance_confidence,
          compliance_factors: sc?.compliance_factors,
          purpose: sc?.purpose || sc?.description,
          description: sc?.description || sc?.purpose,
          languages: sc?.languages,
          frameworks: sc?.frameworks,
          repository_url: sc?.repository_url,
          git: sc?.git,
          external_dependencies: sc?.external_dependencies,
          documentation_quality: sc?.documentation_quality,
          deployment_targets: sc?.deployment_targets,
          last_commit_date: sc?.last_commit_date,
          commit_count_30d: sc?.commit_count_30d,
          commit_count_90d: sc?.commit_count_90d,
          actors: sc?.actors,
        },
        level: selectedLevel,
      });
    }

    const effectiveEntities = allEntities.map((entity) => {
      const override = reviewOverrides[entity.id];
      if (!override) {
        return entity;
      }

      return {
        ...entity,
        attributes: {
          ...(entity.attributes || {}),
          ...override,
        },
      };
    });

    // Filter entities
    let filteredEntities = effectiveEntities.filter((e) => {
      const typeMatch =
        selectedEntityTypes.length === 0 ||
        selectedEntityTypes.includes(e.entity_type);
      const externalMatch = showExternal || !e.attributes?.is_external;
      const searchMatch =
        searchTerm === "" ||
        e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        e.file_path?.toLowerCase().includes(searchTerm.toLowerCase());

      // NEW: Dependency type filter for C4 Context level
      let dependencyTypeMatch = true;
      if (selectedLevel === "context_level" && e.attributes?.is_external) {
        const depType = e.attributes?.dependency_type;
        if (dependencyViewFilter === "business") {
          dependencyTypeMatch = depType === "BUSINESS_SYSTEM";
        } else if (dependencyViewFilter === "technical") {
          dependencyTypeMatch = depType === "TECHNICAL_INFRA";
        }
        // 'all' shows everything
      }

      return typeMatch && externalMatch && searchMatch && dependencyTypeMatch;
    });

    // Create entity lookup
    const entityIds = new Set(filteredEntities.map((e) => e.id));

    // Filter relationships
    const filteredRelationships = allRelationships.filter((r) => {
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
      selectedLevel === "component_level" &&
      filteredEntities.some((e) => e.entity_type === "component")
    ) {
      const componentEntities = filteredEntities.filter(
        (e) => e.entity_type === "component",
      );

      // Group components by their actual container attribute
      const containerGroups = new Map<string, typeof componentEntities>();
      componentEntities.forEach((comp) => {
        const containerName =
          (comp.attributes?.container as string) || "Unknown";

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
          (c: any) => c.name === containerName,
        );
        const displayName = containerInfo?.name || containerName;
        const containerType = containerInfo?.container_type || "Service";
        const technology = containerInfo?.technology || "Unknown";

        // Create container parent node
        const containerNode: Node = {
          id: `container_frame_${containerName}`,
          type: "container",
          position: { x: currentX, y: 100 },
          data: {
            label: displayName,
            containerType: containerType,
            technology: technology,
          },
          style: {
            width: 700,
            height: Math.max(500, Math.ceil(components.length / 2) * 150 + 150),
            backgroundColor: "rgba(99, 102, 241, 0.05)",
            border: "2px solid #6366f1",
            borderRadius: "12px",
            padding: "20px",
          },
        };
        rfNodes.push(containerNode);

        // Add component nodes as children
        components.forEach((e, idx) => {
          let shortName = e.name.includes(".")
            ? e.name.split(".").pop() || e.name
            : e.name;

          const typeSuffixes = [
            "Class",
            "Function",
            "Method",
            "Module",
            "File",
            "Variable",
            "Constant",
          ];
          typeSuffixes.forEach((suffix) => {
            if (shortName.endsWith(suffix) && shortName !== suffix) {
              shortName = shortName.slice(0, -suffix.length);
            }
          });

          shortName = shortName.replace(/[._]+$/, "");
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
            type: "custom",
            position: {
              x: childStartX + col * (220 + childSpacing),
              y: childStartY + row * (120 + childSpacing),
            },
            parentNode: containerNode.id,
            extent: "parent",
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
        (e) => e.entity_type !== "component",
      );
      nonComponents.forEach((e) => {
        let shortName = e.name.includes(".")
          ? e.name.split(".").pop() || e.name
          : e.name;

        const typeSuffixes = [
          "Class",
          "Function",
          "Method",
          "Module",
          "File",
          "Variable",
          "Constant",
        ];
        typeSuffixes.forEach((suffix) => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });

        shortName = shortName.replace(/[._]+$/, "");
        const displayType =
          e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);

        rfNodes.push({
          id: e.id,
          type: "custom",
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
      const hasContainerLevel = selectedLevel === "container_level";
      const containerEntities = filteredEntities.filter(
        (e) => e.entity_type === "container",
      );
      const containerInfoByName = new Map(
        (architecture?.containers || []).map((container: any) => [
          container.name,
          container,
        ]),
      );

      const isKubernetesEntity = (entity: CodeEntity) => {
        const tech = String(entity.language || "").toLowerCase();
        const containerType = String(
          entity.attributes?.container_type || "",
        ).toLowerCase();
        const runtimeEnv = String(
          entity.attributes?.runtime_environment || "",
        ).toLowerCase();
        const deployment = String(
          entity.attributes?.deployment || "",
        ).toLowerCase();

        return (
          tech.includes("kubernetes") ||
          containerType.includes("helm") ||
          containerType.includes("kubernetes") ||
          runtimeEnv.includes("kubernetes") ||
          deployment.includes("helm") ||
          deployment.includes("kustomize") ||
          deployment.includes("manifest")
        );
      };

      let clusterNodeId: string | null = null;

      if (hasContainerLevel && containerEntities.length > 0) {
        const kubernetesContainers =
          containerEntities.filter(isKubernetesEntity);

        if (kubernetesContainers.length > 0) {
          const columns = Math.min(
            4,
            Math.max(2, Math.ceil(kubernetesContainers.length / 2)),
          );
          const rows = Math.ceil(kubernetesContainers.length / columns);
          const clusterWidth = Math.max(720, columns * 240 + 200);
          const clusterHeight = Math.max(420, rows * 140 + 180);
          const clusterMeta = architecture?.metadata?.runtime?.cluster;
          clusterNodeId = "cluster_kubernetes";
          rfNodes.push({
            id: clusterNodeId,
            type: "container",
            position: { x: 80, y: 80 },
            className: "cluster-frame",
            draggable: false,
            selectable: false,
            data: {
              label: "Kubernetes Cluster",
              containerType: "Runtime Environment",
              technology: "Kubernetes",
              clusterMeta,
            },
            style: {
              width: clusterWidth,
              height: clusterHeight,
              backgroundColor: "rgba(148, 163, 184, 0.08)",
              border: "2px dashed #cbd5e1",
              borderRadius: "16px",
              padding: "20px",
              pointerEvents: "none",
            },
          });
        }
      }

      // Original logic for non-component entities
      filteredEntities.forEach((e) => {
        let shortName = e.name.includes(".")
          ? e.name.split(".").pop() || e.name
          : e.name;

        const typeSuffixes = [
          "Class",
          "Function",
          "Method",
          "Module",
          "File",
          "Variable",
          "Constant",
        ];
        typeSuffixes.forEach((suffix) => {
          if (shortName.endsWith(suffix) && shortName !== suffix) {
            shortName = shortName.slice(0, -suffix.length);
          }
        });

        shortName = shortName.replace(/[._]+$/, "");
        const displayType =
          e.entity_type.charAt(0).toUpperCase() + e.entity_type.slice(1);

        const containerInfo =
          e.entity_type === "container"
            ? containerInfoByName.get(e.name)
            : null;

        const node: Node = {
          id: e.id,
          type: "custom",
          position: { x: 0, y: 0 },
          ...(e.entity_type === "system"
            ? { style: { width: 230, minHeight: 80 } }
            : {}),
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
            containerMeta: containerInfo
              ? {
                  owner: containerInfo.owner,
                  owner_team: containerInfo.owner_team,
                  container_type: containerInfo.container_type,
                  technology: containerInfo.technology,
                  protocol: containerInfo.protocol,
                  runtime_info: containerInfo.runtime_info,
                  runtime_environment: containerInfo.runtime_environment,
                  deployment: containerInfo.deployment,
                  tier: containerInfo.tier,
                  data_class: containerInfo.data_class,
                  status: containerInfo.status,
                  active_experts: containerInfo.active_experts,
                  compliance: containerInfo.compliance,
                  compliance_confidence: containerInfo.compliance_confidence,
                  compliance_factors: containerInfo.compliance_factors,
                  description: containerInfo.description,
                  llm_description: containerInfo.llm_description,
                  health_endpoint: containerInfo.health_endpoint,
                  repository_url: containerInfo.repository_url,
                }
              : undefined,
          },
        };

        if (
          clusterNodeId &&
          e.entity_type === "container" &&
          isKubernetesEntity(e)
        ) {
          node.parentNode = clusterNodeId;
          node.extent = "parent";
        }

        rfNodes.push(node);
      });
    }

    const isContextLevel = selectedLevel === "context_level";
    const rfEdges = buildRenderedEdges(
      filteredRelationships,
      isContextLevel,
      filteredEntities,
    );

    // Build context external entities from system_context for linking container edges to context-level externals
    const contextExternalEntities = (
      architecture.system_context?.external_dependencies || []
    ).map((dep: any, idx: number) => ({
      id: `context_external_${idx}`,
      name: dep.context_name || dep.name,
      entity_type: "external_system",
    }));

    const { nodes: ghostNodes, edges: dependencyEdges } =
      selectedLevel === "container_level" &&
      (architecture?.containers?.length > 0 ||
        (architecture?.relationships?.containers?.length ?? 0) > 0)
        ? generateC4Edges(
            architecture?.containers || [],
            architecture?.relationships?.containers || [],
            contextExternalEntities,
          )
        : { nodes: [], edges: [] };

    const mergedEdges = [...rfEdges, ...dependencyEdges];
    const mergedNodes = [...rfNodes, ...ghostNodes];

    // Apply layout — use star layout for C4 context level, dagre for everything else
    let layoutedNodes: Node[];
    let layoutedEdges: Edge[];
    if (selectedLevel === "context_level") {
      layoutedNodes = layoutContextLevel([...mergedNodes]);
      layoutedEdges = mergedEdges;
    } else {
      const result = getLayoutedElements(mergedNodes, mergedEdges);
      layoutedNodes = result.nodes;
      layoutedEdges = result.edges;
    }

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
                padding: 0.2,
                includeHiddenNodes: false,
                duration: attempt === 1 ? 600 : 400,
                maxZoom: 1.5,
                minZoom: 0.5,
              });
            } catch (e) {
              console.warn(
                `[CodeArchitectureViewer] fitView attempt ${attempt} error:`,
                e,
              );
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
    dependencyViewFilter,
    searchTerm,
    reviewOverrides,
    fitView,
  ]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedEdge(null);
    setEdgeDescription("");
    setSelectedNode(node.data);

    // All descriptions must be precomputed - no LLM calls
    const precomputedDescription =
      node.data?.containerMeta?.llm_description ||
      node.data?.containerMeta?.description ||
      node.data?.llm_description ||
      node.data?.attributes?.llm_description ||
      node.data?.attributes?.description ||
      node.data?.attributes?.purpose;

    setNodeDescription(normalizeDescription(precomputedDescription) || "");
    setIsNodeLoading(false);
  }, []);

  const buildArchitectureChatContext = useCallback(() => {
    const system = architecture?.system_context || {};

    return {
      selectedLevel,
      system: {
        name: system.name,
        purpose: system.purpose || system.description,
        business_domain: system.business_domain || system.domain,
        owner_team: system.owner_team || system.owner,
        repository_url: system.repository_url,
      },
      counts: {
        nodes: nodes.length,
        edges: edges.length,
        containers: architecture?.containers?.length || 0,
        components: architecture?.components?.length || 0,
        context_relationships:
          architecture?.relationships?.context?.length || 0,
        container_relationships:
          architecture?.relationships?.containers?.length || 0,
      },
    };
  }, [architecture, edges.length, nodes.length, selectedLevel]);

  const getNodeReviewOverride = useCallback(
    (nodeId?: string | null) => {
      if (!nodeId) {
        return undefined;
      }
      return reviewOverrides[nodeId];
    },
    [reviewOverrides],
  );

  const mergeNodeReviewOverride = useCallback(
    (node: any) => {
      if (!node) {
        return node;
      }

      const override = getNodeReviewOverride(node.id);
      if (!override) {
        return node;
      }

      return {
        ...node,
        attributes: {
          ...(node.attributes || {}),
          ...override,
        },
      };
    },
    [getNodeReviewOverride],
  );

  const buildSelectionChatContext = useCallback(() => {
    const reviewedSelectedNode = mergeNodeReviewOverride(selectedNode);

    if (selectedEdge && !reviewedSelectedNode) {
      return {
        kind: "edge",
        edge: {
          id: selectedEdge.id,
          source: selectedEdge.source,
          target: selectedEdge.target,
          label:
            typeof selectedEdge.label === "string"
              ? selectedEdge.label
              : undefined,
          data: selectedEdge.data,
          description:
            edgeDescription ||
            selectedEdge?.data?.description ||
            selectedEdge?.data?.llm_description,
        },
      };
    }

    if (reviewedSelectedNode) {
      return {
        kind: "node",
        node: {
          id: reviewedSelectedNode.id,
          name: reviewedSelectedNode.name,
          label: reviewedSelectedNode.label,
          type: reviewedSelectedNode.type,
          level: reviewedSelectedNode.level,
          file: reviewedSelectedNode.file,
          attributes: reviewedSelectedNode.attributes,
          containerMeta: reviewedSelectedNode.containerMeta,
          description:
            nodeDescription ||
            reviewedSelectedNode?.attributes?.purpose ||
            reviewedSelectedNode?.attributes?.description ||
            reviewedSelectedNode?.containerMeta?.description,
        },
      };
    }

    return { kind: "overview" };
  }, [
    edgeDescription,
    mergeNodeReviewOverride,
    nodeDescription,
    selectedEdge,
    selectedNode,
  ]);

  const handleArchitectureChat = useCallback(
    async (message: string) => {
      const trimmedMessage = message.trim();
      if (!trimmedMessage) {
        return;
      }

      const historyForRequest = chatMessages.slice(-8);
      setChatMessages((currentMessages) => [
        ...currentMessages,
        { role: "user", content: trimmedMessage },
      ]);
      setIsChatLoading(true);

      try {
        let streamedReply = "";
        let receivedDelta = false;

        await codeArchitectureAPI.streamChatWithContext(
          {
            message: trimmedMessage,
            history: historyForRequest,
            selection: buildSelectionChatContext(),
            architecture: buildArchitectureChatContext(),
          },
          {
            onDelta: (delta) => {
              if (!delta) {
                return;
              }
              receivedDelta = true;
              streamedReply += delta;
            },
            onComplete: () => {
              setChatMessages((currentMessages) => {
                if (!receivedDelta) {
                  return [
                    ...currentMessages,
                    {
                      role: "assistant",
                      content: "No response available.",
                    },
                  ];
                }

                return [
                  ...currentMessages,
                  {
                    role: "assistant",
                    content: streamedReply.trim() || "No response available.",
                  },
                ];
              });
            },
          },
        );
      } catch (error) {
        setChatMessages((currentMessages) => [
          ...currentMessages,
          {
            role: "assistant",
            content: "Unable to reach the local model right now.",
          },
        ]);
      } finally {
        setIsChatLoading(false);
      }
    },
    [buildArchitectureChatContext, buildSelectionChatContext, chatMessages],
  );

  const handleApplyReviewDecision = useCallback(
    (decision: DependencyReviewDecision) => {
      const reviewedNodeName =
        selectedNode?.id === decision.nodeId
          ? selectedNode.name
          : decision.nodeId;
      const reviewerSummary =
        decision.description ||
        `Human review classified ${reviewedNodeName} as ${decision.label}.`;

      setReviewOverrides((current) => ({
        ...current,
        [decision.nodeId]: {
          dependency_type: decision.value,
          decision_mode: "human_reviewed",
          review_status: "approved",
          requires_human_review: false,
          human_review_choice: decision.label,
          human_review_summary: reviewerSummary,
        },
      }));

      setChatMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "user",
          content: `Review decision: ${decision.label}`,
        },
        {
          role: "assistant",
          content: `${reviewedNodeName}: ${reviewerSummary}`,
        },
      ]);
    },
    [selectedNode],
  );

  const onEdgeClick = useCallback(
    async (_event: React.MouseEvent, edge: Edge) => {
      setSelectedNode(null);
      setNodeDescription("");
      setSelectedEdge(edge);
      setEdgeDescription("");
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
          label: typeof edge.label === "string" ? edge.label : undefined,
          relationshipType:
            (edge as any)?.data?.relationship_type || (edge as any)?.data?.type,
          protocol: typeof edge.label === "string" ? edge.label : undefined,
        });
        setEdgeDescription(
          response?.description || "No description available.",
        );
      } catch (error) {
        setEdgeDescription("Unable to generate description right now.");
      } finally {
        setIsEdgeLoading(false);
      }
    },
    [],
  );

  const avgConnections =
    nodes.length > 0 ? (edges.length / nodes.length).toFixed(1) : "0";

  const toggleLevel = (level: string) => {
    setSelectedLevel(level);
  };

  const toggleRelationshipType = (type: string) => {
    const next = selectedRelationshipTypes.includes(type)
      ? selectedRelationshipTypes.filter((t) => t !== type)
      : [...selectedRelationshipTypes, type];
    setSelectedRelationshipTypes(next);
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
          <p className="hint">
            Run extraction above or execute{" "}
            <code>python -m services.code_extraction.c4_extractor</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-architecture-viewer">
      <div className="viewer-topbar">
        <ArchitectureHeader
          nodeCount={nodes.length}
          edgeCount={edges.length}
          avgConnections={avgConnections}
        />

        <MetricsBar
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          selectedLevel={selectedLevel}
          toggleLevel={toggleLevel}
          relationshipTypes={relationshipTypes}
          selectedRelationshipTypes={selectedRelationshipTypes}
          toggleRelationshipType={toggleRelationshipType}
          showExternal={showExternal}
          setShowExternal={setShowExternal}
          dependencyViewFilter={dependencyViewFilter}
          setDependencyViewFilter={setDependencyViewFilter}
          repoSectionExpanded={repoSectionExpanded}
          setRepoSectionExpanded={setRepoSectionExpanded}
          githubUrl={githubUrl}
          setGithubUrl={setGithubUrl}
          localPath={localPath}
          setLocalPath={setLocalPath}
          isExtracting={isExtracting}
          handleExtractFromGithub={handleExtractFromGithub}
          handleScanLocalPath={handleScanLocalPath}
          handleBatchExtract={handleBatchExtract}
          handleGitHubOrgScan={handleGitHubOrgScan}
          setArchitecture={setArchitecture}
          setNodes={setNodes}
          setEdges={setEdges}
          setExtractionStatus={setExtractionStatus}
          setExtractionError={setExtractionError}
          extractionStatus={extractionStatus}
          extractionError={extractionError}
        />
      </div>

      <div className="viewer-layout">
        <GraphView
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          selectedLevel={selectedLevel}
        />

        <div className="chat-panel-container">
          {selectedEdge && !selectedNode ? (
            <EdgeDetailsPanel
              selectedEdge={selectedEdge}
              onClose={() => setSelectedEdge(null)}
              edgeDescription={edgeDescription}
              isEdgeLoading={isEdgeLoading}
              chatMessages={chatMessages}
              isChatLoading={isChatLoading}
              onSendChat={handleArchitectureChat}
            />
          ) : (
            <NodeDetailsPanel
              selectedNode={mergeNodeReviewOverride(selectedNode)}
              onClose={() => setSelectedNode(null)}
              nodeDescription={nodeDescription}
              isNodeLoading={isNodeLoading}
              chatMessages={chatMessages}
              isChatLoading={isChatLoading}
              onSendChat={handleArchitectureChat}
              onApplyReviewDecision={handleApplyReviewDecision}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default CodeArchitectureViewer;
