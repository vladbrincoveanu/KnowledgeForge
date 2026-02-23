import React, { useEffect, useReducer, useCallback, useRef } from 'react';
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import axios from 'axios';
import './CodeArchitectureViewer.scss';
import { codeArchitectureAPI } from '../../../services/api';
import CustomNode from './CustomNode';
import ContainerNode from './ContainerNode';
import C4Edge from './C4Edge';
import ArchitectureHeader from './components/ArchitectureHeader';
import FiltersSidebar from './components/FiltersSidebar';
import GraphView from './components/GraphView';
import NodeDetailsPanel from './components/NodeDetailsPanel';
import EdgeDetailsPanel from './components/EdgeDetailsPanel';
import ExportPreviewDialog from './components/ExportPreviewDialog';
import ContextReviewDialog, {
  type ContextFeedbackPayload,
} from './components/ContextReviewDialog';

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

const HUMAN_RELATIONSHIP_LABELS: Record<string, string> = {
  uses: 'Uses',
  uses_external_service: 'Uses',
  contains: 'Contains',
  depends_on: 'Depends on',
  calls: 'Calls API',
  invokes: 'Invokes',
  reads_from: 'Reads data from',
  writes_to: 'Writes data to',
  publishes_to: 'Publishes events to',
  subscribes_to: 'Consumes events from',
  sends_to: 'Sends data to',
  receives_from: 'Receives data from',
  authenticates_with: 'Authenticates with',
  reports_to: 'Reports updates to',
};

const toHumanLabel = (value?: string) =>
  String(value || '')
    .trim()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());

const humanizeNodeName = (value?: string) =>
  String(value || '')
    .replace(/^:+/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const isTechnicalRelationshipText = (value?: string) => {
  const text = normalizeDescription(value).toLowerCase();
  if (!text) return true;

  if (/^[a-z0-9_:/.-]+$/.test(text) && text.includes('_')) return true;
  if (/^[a-z0-9_:/.-]+$/.test(text) && !text.includes(' ')) return true;
  if (
    [
      'uses external service',
      'uses',
      'depends on',
      'calls',
      'invokes',
      'contains',
    ].includes(text)
  ) {
    return true;
  }

  return false;
};

type InferredAction = { verb: string; prep: 'to' | 'via' | 'in' | 'with' };

const inferBusinessActionFromTarget = (targetName?: string): InferredAction | null => {
  const name = String(targetName || '').toLowerCase();
  if (!name) return null;
  if (/(analytics|mixpanel|ga4|google analytics)/.test(name))
    return { verb: 'Analyzes product behavior', prep: 'in' };
  if (/(sentry|monitor|observability|datadog|new relic)/.test(name))
    return { verb: 'Tracks errors', prep: 'in' };
  if (/(stripe|paypal|billing|payment)/.test(name))
    return { verb: 'Processes payments', prep: 'via' };
  if (/(mail|email|resend|sendgrid|smtp)/.test(name))
    return { verb: 'Sends customer emails', prep: 'via' };
  if (/(slack|teams|chat|pagerduty)/.test(name))
    return { verb: 'Sends alerts', prep: 'to' };
  if (/(github|gitlab|npm|registry|bitbucket)/.test(name))
    return { verb: 'Publishes packages', prep: 'to' };
  if (/(redis|mongo|postgres|mysql|database|sql|s3|storage|bucket)/.test(name))
    return { verb: 'Stores operational data', prep: 'in' };
  return null;
};

const isLocalOrEmptyUrl = (url?: string) => {
  const v = String(url || '').toLowerCase().trim();
  if (!v) return true;
  return (
    v.startsWith('http://localhost') ||
    v.startsWith('https://localhost') ||
    v.startsWith('http://127.0.0.1') ||
    v.startsWith('https://127.0.0.1') ||
    v.startsWith('http://0.0.0.0') ||
    v.startsWith('https://0.0.0.0')
  );
};

const isDockerDerivedContextExternal = (entity: CodeEntity) => {
  if (!entity.attributes?.is_external) return false;

  const name = String(entity.name || '').trim();
  const filePath = String(entity.file_path || '').toLowerCase();
  const detectedFrom = String(entity.attributes?.detected_from || '').toLowerCase();
  const url = String(entity.attributes?.url || '').trim();

  // If it has a real URL, treat as external.
  if (url && !isLocalOrEmptyUrl(url)) return false;

  // Docker/compose-derived "externals" should not appear at Context level.
  if (/dockerfile|docker-compose|compose\.ya?ml/.test(filePath)) return true;
  if (/dockerfile|docker-compose|compose\.ya?ml/.test(detectedFrom)) return true;

  // Ports like ":40121" are almost certainly internal service bindings.
  if (/^:?\d{2,5}$/.test(name)) return true;

  return false;
};

const inferDependencyTypeForContext = (dep: any): 'BUSINESS_SYSTEM' | 'TECHNICAL_INFRA' | 'UNKNOWN' => {
  const explicit = String(dep?.dependency_type || '').toUpperCase();
  if (explicit === 'BUSINESS_SYSTEM' || explicit === 'TECHNICAL_INFRA') {
    return explicit as any;
  }

  const depType = String(dep?.type || '').toLowerCase();
  if (['database', 'cache', 'queue', 'messaging', 'logging', 'monitoring', 'observability', 'storage', 'search', 'rpc'].includes(depType)) {
    return 'TECHNICAL_INFRA';
  }

  const name = `${dep?.name || ''} ${dep?.service || ''}`.toLowerCase();
  if (
    /(sql server|postgres|postgresql|mysql|mariadb|mongodb|redis|kafka|rabbitmq|elasticsearch|opensearch|s3|bucket)/.test(name)
  ) return 'TECHNICAL_INFRA';
  if (/(serilog|opentelemetry|datadog|prometheus|grafana|new relic)/.test(name))
    return 'TECHNICAL_INFRA';
  if (/(proget|artifactory|nexus|nuget|npm registry|package registry)/.test(name))
    return 'TECHNICAL_INFRA';

  return 'BUSINESS_SYSTEM';
};

const isDockerishExternalDependency = (dep: any) => {
  const name = String(dep?.name || '').trim();
  const detectedFrom = String(dep?.detected_from || '').toLowerCase();
  const url = String(dep?.url || '').toLowerCase();
  const depType = String(dep?.type || '').toLowerCase();
  const depClass = String(dep?.dependency_type || '').toUpperCase();

  if (!name) return true;
  if (/^:?\d{2,5}$/.test(name)) return true;
  // Keep technical platforms even if inferred from docker/compose (we only drop raw docker artifacts).
  const looksLikeTechPlatform =
    depClass === 'TECHNICAL_INFRA' ||
    ['database', 'cache', 'messaging', 'queue', 'logging', 'monitoring', 'observability', 'storage', 'search'].includes(
      depType
    );
  if (!looksLikeTechPlatform && /dockerfile|docker-compose|compose\.ya?ml/.test(detectedFrom))
    return true;
  if (url && isLocalOrEmptyUrl(url)) {
    // Local-only + docker-derived path is a strong internal signal.
    if (!looksLikeTechPlatform && /dockerfile|docker-compose|compose\.ya?ml/.test(detectedFrom))
      return true;
  }
  return false;
};

const buildBusinessRelationshipCopy = (
  relationshipType?: string,
  description?: string,
  sourceName?: string,
  targetName?: string,
  sourceType?: string,
  targetType?: string
) => {
  const source = humanizeNodeName(sourceName || 'This system');
  const target = humanizeNodeName(targetName || 'external system');
  const fromType = String(sourceType || '').toLowerCase();
  const toType = String(targetType || '').toLowerCase();
  const normalizedDescription = normalizeDescription(description).replace(
    /[_-]+/g,
    ' '
  );

  if (fromType === 'person' && toType === 'system') {
    return {
      label: 'Uses product',
      sentence: `${source} uses ${target} to perform business workflows.`,
    };
  }

  if (fromType === 'system' && toType === 'person') {
    return {
      label: 'Provides updates',
      sentence: `${source} provides updates to ${target}.`,
    };
  }

  if (
    normalizedDescription &&
    !isTechnicalRelationshipText(normalizedDescription) &&
    normalizedDescription.length <= 110
  ) {
    const trimmed = normalizedDescription.replace(/[.;:]+$/, '');
    return {
      label:
        trimmed.length > 46 ? `${trimmed.slice(0, 43).trim()}...` : trimmed,
      sentence: `${source}: ${trimmed}.`,
    };
  }

  const inferred = inferBusinessActionFromTarget(targetName);
  if (inferred) {
    const label = `${inferred.verb} ${inferred.prep} ${target}`.slice(0, 46);
    return {
      label,
      sentence: `${source} ${inferred.verb.toLowerCase()} ${inferred.prep} ${target}.`,
    };
  }

  const relKey = String(relationshipType || '')
    .trim()
    .toLowerCase();
  const baseFallbackLabel =
    HUMAN_RELATIONSHIP_LABELS[relKey] ||
    toHumanLabel(relationshipType) ||
    'Interacts with';
  const includeTargetInLabel =
    ['Uses', 'Depends on', 'Interacts with', 'Integrates with'].includes(baseFallbackLabel) &&
    target &&
    target.toLowerCase() !== 'external system';
  const fallbackLabel = includeTargetInLabel
    ? `${baseFallbackLabel} ${target}`.slice(0, 46)
    : baseFallbackLabel;
  return {
    label: fallbackLabel,
    sentence: `${source} ${baseFallbackLabel.toLowerCase()} ${target}.`,
  };
};

const CONTEXT_FEEDBACK_STORAGE_PREFIX = 'kf_context_feedback:';

const makeContextFeedbackRepoKey = (githubUrl?: string, localPath?: string) => {
  const gh = String(githubUrl || '').trim();
  if (gh) return `github:${gh}`;
  const lp = String(localPath || '').trim();
  if (lp) return `local:${lp}`;
  return 'unknown';
};

const loadStoredContextFeedback = (repoKey: string): ContextFeedbackPayload | null => {
  try {
    const raw = window.localStorage.getItem(`${CONTEXT_FEEDBACK_STORAGE_PREFIX}${repoKey}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed as ContextFeedbackPayload;
  } catch {
    return null;
  }
};

const persistStoredContextFeedback = (repoKey: string, payload: ContextFeedbackPayload) => {
  try {
    window.localStorage.setItem(
      `${CONTEXT_FEEDBACK_STORAGE_PREFIX}${repoKey}`,
      JSON.stringify(payload)
    );
  } catch {
    // ignore storage failures (private mode, quota, etc.)
  }
};

const needsHumanContextReview = (results: any) => {
  const sc = results?.system_context || {};
  const actors = Array.isArray(sc.actors) ? sc.actors : [];
  const deps = Array.isArray(sc.external_dependencies) ? sc.external_dependencies : [];
  const contextRels = Array.isArray(results?.relationships?.context)
    ? results.relationships.context
    : [];

  const hasSuspiciousDeps = deps.some((d: any) => {
    const name = String(d?.name || '').trim();
    const detectedFrom = String(d?.detected_from || '').toLowerCase();
    if (!name || /^:?\d{2,5}$/.test(name)) return true;
    if (/dockerfile|docker-compose|compose\.ya?ml/.test(detectedFrom)) return true;
    return false;
  });

  const hasGenericRelationships = contextRels.some((r: any) => {
    const desc = normalizeDescription(r?.description);
    const type = String(r?.relationship_type || r?.type || '').trim();
    if (isTechnicalRelationshipText(desc)) return true;
    if (!desc && (!type || type.toLowerCase() === 'uses')) return true;
    return false;
  });

  const hasNoActors = actors.length === 0;
  return hasSuspiciousDeps || hasGenericRelationships || hasNoActors;
};

const buildInitialContextFeedbackPayload = (
  results: any,
  repoKey: string
): ContextFeedbackPayload => {
  const sc = results?.system_context || {};
  const systemName = String(sc?.name || '').trim();

  const stored = loadStoredContextFeedback(repoKey);
  const storedActors = Array.isArray(stored?.actors) ? stored?.actors : [];
  const storedDeps = Array.isArray(stored?.external_dependencies)
    ? stored?.external_dependencies
    : [];

  const actors = (Array.isArray(sc.actors) ? sc.actors : []).map((a: any, idx: number) => {
    const previous = storedActors.find(x => x.index === idx);
    return {
      index: idx,
      name: previous?.name ?? a?.name ?? '',
      description: previous?.description ?? a?.description ?? a?.role ?? '',
      ignore: previous?.ignore ?? false,
    };
  });

  const rawDeps = Array.isArray(sc.external_dependencies) ? sc.external_dependencies : [];
  const keptDepIndexes = new Set<number>();
  const deps = rawDeps
    .map((d: any, idx: number) => ({ d, idx }))
    .filter(({ d }) => !isDockerishExternalDependency(d)) // drop internal/docker noise entirely
    .map(({ d, idx }) => {
      keptDepIndexes.add(idx);
      const previous = storedDeps.find(x => x.index === idx);
      const inferred = inferDependencyTypeForContext(d);
      const depType = previous?.dependency_type ?? inferred;
      return {
        index: idx,
        name: previous?.name ?? d?.name ?? d?.service ?? '',
        dependency_type: depType,
        url: previous?.url ?? d?.url ?? '',
        protocol: previous?.protocol ?? d?.protocol ?? '',
        notes: previous?.notes ?? '',
        ignore: previous?.ignore ?? false,
      };
    });

  const droppedDepNames = new Set<string>(
    rawDeps
      .map((d: any) => String(d?.name || d?.service || '').trim())
      .filter((n: string, idx: number) => n && !keptDepIndexes.has(idx))
  );

  const rels = (Array.isArray(results?.relationships?.context)
    ? results.relationships.context
    : []
  )
    .map((r: any) => {
    const src = String(r?.source || r?.from || '').trim();
    const dst = String(r?.destination || r?.to || '').trim();
    const relType = String(r?.relationship_type || r?.type || 'uses');
    const descRaw = normalizeDescription(r?.description);
    const suggested = buildBusinessRelationshipCopy(relType, descRaw, src, dst);
    const desc =
      descRaw && !isTechnicalRelationshipText(descRaw) ? descRaw : suggested.label || 'Uses';
    return {
      source: src,
      destination: dst,
      description: desc,
      relationship_type: relType || 'uses',
      protocol: String(r?.protocol || '').trim() || undefined,
    };
  })
    // drop relationships pointing to removed docker-ish deps
    .filter((r: any) => !droppedDepNames.has(String(r?.destination || '').trim()));

  return {
    system_name: (stored?.system_name ?? systemName) || undefined,
    actors,
    external_dependencies: deps,
    relationships: rels,
  };
};

const isTechnicalContextNode = (node: Node) => {
  if (node.data?.attributes?.platform_boundary) return true;
  const depType = String(node.data?.attributes?.dependency_type || '').toUpperCase();
  if (depType === 'TECHNICAL_INFRA') return true;
  if (depType === 'BUSINESS_SYSTEM') return false;

  const type = String(node.data?.type || '').toLowerCase();
  if (['database', 'cache', 'messaging', 'logging', 'queue'].includes(type)) {
    return true;
  }

  const fullText = `${node.data?.label || ''} ${node.data?.fullName || ''}`.toLowerCase();
  return /(redis|mongo|postgres|mysql|database|sql|kafka|rabbitmq|queue|cache|s3|storage|serilog|grafana|prometheus|cloudwatch|datadog)/.test(
    fullText
  );
};

const isTechnicalContextEntity = (entity: CodeEntity) => {
  const attrs = entity.attributes || {};
  if (attrs.platform_boundary) return true;

  const depType = String(attrs.dependency_type || '').toUpperCase();
  if (depType === 'TECHNICAL_INFRA') return true;
  if (depType === 'BUSINESS_SYSTEM') return false;

  const type = String(entity.entity_type || '').toLowerCase();
  if (['database', 'cache', 'messaging', 'logging', 'queue'].includes(type)) {
    return true;
  }

  const fullText = `${entity.name || ''} ${attrs.detected_from || ''}`.toLowerCase();
  return /(redis|mongo|postgres|mysql|database|sql|kafka|rabbitmq|queue|cache|s3|storage|serilog|grafana|prometheus|cloudwatch|datadog)/.test(
    fullText
  );
};

const sortNodesByLabel = (a: Node, b: Node) =>
  String(a.data?.label || a.id).localeCompare(String(b.data?.label || b.id));

const getNodeSize = (node: Node) => {
  const width =
    typeof node.style?.width === 'number'
      ? node.style.width
      : node.data?.type === 'system'
        ? 230
        : 220;
  const height =
    typeof node.style?.height === 'number'
      ? node.style.height
      : node.data?.type === 'system'
        ? 90
        : 100;
  return { width, height };
};

const getBounds = (nodes: Node[]) => {
  if (nodes.length === 0) return null;

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  nodes.forEach(node => {
    const { width, height } = getNodeSize(node);
    minX = Math.min(minX, node.position.x);
    minY = Math.min(minY, node.position.y);
    maxX = Math.max(maxX, node.position.x + width);
    maxY = Math.max(maxY, node.position.y + height);
  });

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
};

const _createContextGroupFrame = (
  id: string,
  label: string,
  kind: 'actors' | 'system' | 'business' | 'technical',
  nodes: Node[]
): Node | null => {
  const bounds = getBounds(nodes);
  if (!bounds) return null;

  const padX = kind === 'system' ? 42 : 58;
  const padY = kind === 'system' ? 32 : 46;

  const frameColors: Record<string, { bg: string; border: string; type: string }> = {
    actors: {
      bg: 'rgba(14, 116, 144, 0.05)',
      border: '#67e8f9',
      type: 'Human interactions',
    },
    system: {
      bg: 'rgba(37, 99, 235, 0.06)',
      border: '#93c5fd',
      type: 'Core product',
    },
    business: {
      bg: 'rgba(71, 85, 105, 0.06)',
      border: '#cbd5e1',
      type: 'External business systems',
    },
    technical: {
      bg: 'rgba(15, 23, 42, 0.05)',
      border: '#94a3b8',
      type: 'Technical infrastructure',
    },
  };

  const color = frameColors[kind];

  return {
    id,
    type: 'container',
    className: `context-group-frame group-${kind}`,
    draggable: false,
    selectable: false,
    connectable: false,
    focusable: false,
    zIndex: 0,
    position: {
      x: bounds.x - padX,
      y: bounds.y - padY,
    },
    data: {
      label,
      containerType: `${nodes.length} node${nodes.length === 1 ? '' : 's'}`,
      technology: color.type,
      isGroup: true,
      groupKind: kind,
    },
    style: {
      width: Math.max(kind === 'system' ? 320 : 360, bounds.width + padX * 2),
      height: Math.max(kind === 'system' ? 170 : 240, bounds.height + padY * 2),
      backgroundColor: color.bg,
      border: `2px dashed ${color.border}`,
      borderRadius: 18,
      pointerEvents: 'none',
    },
  };
};

const nodeTypes = {
  custom: CustomNode,
  container: ContainerNode,
};

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
      ranksep: 100,
      nodesep: 50,
      edgesep: 10,
      marginx: 100,
      marginy: 100,
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

// Context layout with view modes:
// - developer: lanes (actors left, business right, technical lower lane)
// - executive: actors left + external ring around system
function layoutContextLevel(
  nodes: Node[],
  viewMode: 'developer' | 'executive' = 'developer'
): Node[] {
  const cx = 700;
  const cy = 420;
  const system = nodes.find(n => n.data?.type === 'system');
  const persons = nodes.filter(n => n.data?.type === 'person').sort(sortNodesByLabel);
  const externals = nodes.filter(
    n => n.data?.type !== 'system' && n.data?.type !== 'person'
  );
  const technicalExternals = externals
    .filter(isTechnicalContextNode)
    .sort(sortNodesByLabel);
  const businessExternals = externals
    .filter(n => !isTechnicalContextNode(n))
    .sort(sortNodesByLabel);

  if (system) {
    system.position = { x: cx - 130, y: cy - 52 };
    system.sourcePosition = Position.Right;
    system.targetPosition = Position.Left;
  }

  // Actors stacked on the left lane
  const actorStartY = cy - ((persons.length - 1) * 125) / 2;
  persons.forEach((n, i) => {
    n.position = { x: cx - 620, y: actorStartY + i * 125 };
    n.sourcePosition = Position.Right;
    n.targetPosition = Position.Right;
  });

  if (viewMode === 'executive') {
    const ringNodes = [...businessExternals, ...technicalExternals].sort(sortNodesByLabel);
    const radiusX = 470;
    const radiusY = 290;
    const count = Math.max(1, ringNodes.length);
    // Keep left side clearer for actors by skipping a wedge around pi.
    const start = -Math.PI / 2;
    const sweep = Math.PI * 1.6;
    ringNodes.forEach((n, i) => {
      const t = count === 1 ? 0.5 : i / (count - 1);
      const angle = start + t * sweep;
      n.position = {
        x: cx + Math.cos(angle) * radiusX,
        y: cy + Math.sin(angle) * radiusY,
      };
      n.sourcePosition = Position.Left;
      n.targetPosition = Position.Left;
    });
    return nodes;
  }

  // Business systems on the right lane (top-to-mid)
  const bizColSpacing = 260;
  const bizRowSpacing = 118;
  const bizCols = Math.max(1, Math.min(3, Math.ceil(businessExternals.length / 8)));
  const bizRows = Math.ceil(businessExternals.length / bizCols);
  const bizBlockHeight = (bizRows - 1) * bizRowSpacing;
  const bizYStart = cy - bizBlockHeight / 2;
  const bizXStart = cx + 350;
  businessExternals.forEach((n, i) => {
    const col = Math.floor(i / bizRows);
    const row = i % bizRows;
    n.position = {
      x: bizXStart + col * bizColSpacing,
      y: bizYStart + row * bizRowSpacing,
    };
    n.sourcePosition = Position.Left;
    n.targetPosition = Position.Left;
  });

  // Technical platforms on a lower lane
  const techColSpacing = 260;
  const techRowSpacing = 115;
  const techCols = Math.max(1, Math.min(4, technicalExternals.length));
  const techYStart = cy + 250;
  technicalExternals.forEach((n, i) => {
    const row = Math.floor(i / techCols);
    const col = i % techCols;
    const itemsInRow =
      row === Math.floor((technicalExternals.length - 1) / techCols)
        ? ((technicalExternals.length - 1) % techCols) + 1
        : techCols;
    const rowWidth = (itemsInRow - 1) * techColSpacing;
    const xStart = cx - rowWidth / 2;
    n.position = {
      x: xStart + col * techColSpacing,
      y: techYStart + row * techRowSpacing,
    };
    n.sourcePosition = Position.Top;
    n.targetPosition = Position.Top;
  });

  return nodes;
}

function applyExecutiveContainerGrouping(nodes: Node[]): Node[] {
  const containers = nodes.filter(
    node =>
      node.type === 'custom' &&
      node.data?.type === 'container' &&
      !node.parentNode
  );
  if (containers.length <= 1) {
    return nodes;
  }

  const groups = new Map<string, Node[]>();
  containers.forEach(node => {
    const attrs = node.data?.attributes || {};
    const domain = String(attrs.business_domain || attrs.domain || 'Core').trim();
    const squad = String(attrs.squad || attrs.owner || 'Default Squad').trim();
    const key = `${domain}__${squad}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(node);
  });

  if (groups.size <= 1) {
    return nodes;
  }

  const next = [...nodes];
  let groupIdx = 0;
  groups.forEach((groupNodes, key) => {
    const [domain, squad] = key.split('__');
    const frameId = `exec_group_${groupIdx++}`;
    const columns = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(groupNodes.length))));
    const rows = Math.ceil(groupNodes.length / columns);
    const width = Math.max(620, columns * 260 + 80);
    const height = Math.max(330, rows * 150 + 120);

    next.push({
      id: frameId,
      type: 'container',
      className: 'exec-group-frame',
      draggable: false,
      selectable: false,
      connectable: false,
      focusable: false,
      zIndex: 0,
      position: { x: 0, y: 0 },
      data: {
        label: domain,
        containerType: squad,
        technology: 'Domain Cluster',
      },
      style: {
        width,
        height,
        backgroundColor: 'rgba(59, 130, 246, 0.04)',
        border: '2px dashed #93c5fd',
        borderRadius: 14,
        padding: '20px',
      },
    });

    groupNodes.forEach((node, idx) => {
      const row = Math.floor(idx / columns);
      const col = idx % columns;
      node.parentNode = frameId;
      node.extent = 'parent';
      node.position = {
        x: 30 + col * 245,
        y: 70 + row * 130,
      };
    });
  });

  return next;
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
  | { type: 'SET_ARCHITECTURE'; payload: C4Architecture | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

function archReducer(state: ArchState, action: ArchAction): ArchState {
  switch (action.type) {
    case 'SET_ARCHITECTURE': return { ...state, architecture: action.payload };
    case 'SET_LOADING':      return { ...state, loading: action.payload };
    case 'SET_ERROR':        return { ...state, error: action.payload };
    default: return state;
  }
}

interface FilterState {
  selectedLevel: string;
  selectedEntityTypes: string[];
  selectedRelationshipTypes: string[];
  showExternal: boolean;
  graphViewMode: 'developer' | 'executive';
  dependencyViewFilter: 'all' | 'business' | 'technical';
  searchTerm: string;
  relationshipTypes: string[];
}
type FilterAction =
  | { type: 'SET_LEVEL'; payload: string }
  | { type: 'SET_ENTITY_TYPES'; payload: string[] }
  | { type: 'SET_RELATIONSHIP_TYPES'; payload: string[] }
  | { type: 'SET_SHOW_EXTERNAL'; payload: boolean }
  | { type: 'SET_VIEW_MODE'; payload: 'developer' | 'executive' }
  | { type: 'SET_DEPENDENCY_VIEW'; payload: 'all' | 'business' | 'technical' }
  | { type: 'SET_SEARCH_TERM'; payload: string }
  | { type: 'SET_REL_TYPE_LIST'; payload: string[] };

function filterReducer(state: FilterState, action: FilterAction): FilterState {
  switch (action.type) {
    case 'SET_LEVEL':             return { ...state, selectedLevel: action.payload };
    case 'SET_ENTITY_TYPES':      return { ...state, selectedEntityTypes: action.payload };
    case 'SET_RELATIONSHIP_TYPES':return { ...state, selectedRelationshipTypes: action.payload };
    case 'SET_SHOW_EXTERNAL':     return { ...state, showExternal: action.payload };
    case 'SET_VIEW_MODE':         return { ...state, graphViewMode: action.payload };
    case 'SET_DEPENDENCY_VIEW':   return { ...state, dependencyViewFilter: action.payload };
    case 'SET_SEARCH_TERM':       return { ...state, searchTerm: action.payload };
    case 'SET_REL_TYPE_LIST':     return { ...state, relationshipTypes: action.payload };
    default: return state;
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
  | { type: 'SELECT_NODE'; node: any; description: string }
  | { type: 'SET_NODE_DESCRIPTION'; payload: string }
  | { type: 'CLEAR_NODE' }
  | { type: 'SELECT_EDGE'; edge: any }
  | { type: 'SET_EDGE_DESCRIPTION'; payload: string }
  | { type: 'SET_EDGE_LOADING'; payload: boolean }
  | { type: 'CLEAR_EDGE' };

function selectionReducer(state: SelectionState, action: SelectionAction): SelectionState {
  switch (action.type) {
    case 'SELECT_NODE':
      return { ...state, selectedNode: action.node, nodeDescription: action.description,
               isNodeLoading: false, selectedEdge: null, edgeDescription: '' };
    case 'SET_NODE_DESCRIPTION':
      return { ...state, nodeDescription: action.payload, isNodeLoading: false };
    case 'CLEAR_NODE':
      return { ...state, selectedNode: null, nodeDescription: '', isNodeLoading: false };
    case 'SELECT_EDGE':
      return { ...state, selectedEdge: action.edge, edgeDescription: '',
               isEdgeLoading: false, selectedNode: null, nodeDescription: '' };
    case 'SET_EDGE_DESCRIPTION':
      return { ...state, edgeDescription: action.payload, isEdgeLoading: false };
    case 'SET_EDGE_LOADING':
      return { ...state, isEdgeLoading: action.payload };
    case 'CLEAR_EDGE':
      return { ...state, selectedEdge: null, edgeDescription: '', isEdgeLoading: false };
    default: return state;
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

interface ContextReviewState {
  open: boolean;
  taskId: string | null;
  repoKey: string | null;
  pendingResults: any | null;
  initialPayload: ContextFeedbackPayload | null;
  submitting: boolean;
  error: string | null;
}

type ContextReviewAction =
  | { type: 'OPEN'; taskId: string; repoKey: string; results: any; payload: ContextFeedbackPayload }
  | { type: 'CLOSE' }
  | { type: 'SET_SUBMITTING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_PENDING_RESULTS'; payload: any | null };

function contextReviewReducer(
  state: ContextReviewState,
  action: ContextReviewAction
): ContextReviewState {
  switch (action.type) {
    case 'OPEN':
      return {
        open: true,
        taskId: action.taskId,
        repoKey: action.repoKey,
        pendingResults: action.results,
        initialPayload: action.payload,
        submitting: false,
        error: null,
      };
    case 'CLOSE':
      return {
        open: false,
        taskId: null,
        repoKey: null,
        pendingResults: null,
        initialPayload: null,
        submitting: false,
        error: null,
      };
    case 'SET_SUBMITTING':
      return { ...state, submitting: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_PENDING_RESULTS':
      return { ...state, pendingResults: action.payload };
    default:
      return state;
  }
}
type ExtractionAction =
  | { type: 'SET_URL'; payload: string }
  | { type: 'SET_LOCAL_PATH'; payload: string }
  | { type: 'SET_EXTRACTING'; payload: boolean }
  | { type: 'SET_STATUS'; payload: string | null }
  | { type: 'SET_ERROR'; payload: string | null }
  | {
      type: 'SET_EXPORT_PREVIEW';
      payload: {
        open: boolean;
        format: 'structurizr' | 'mermaid';
        filename: string;
        content: string;
      };
    }
  | { type: 'TOGGLE_REPO_SECTION' }
  | { type: 'SET_REPO_EXPANDED'; payload: boolean };

function extractionReducer(state: ExtractionState, action: ExtractionAction): ExtractionState {
  switch (action.type) {
    case 'SET_URL':          return { ...state, githubUrl: action.payload };
    case 'SET_LOCAL_PATH':   return { ...state, localPath: action.payload };
    case 'SET_EXTRACTING':   return { ...state, isExtracting: action.payload };
    case 'SET_STATUS':       return { ...state, extractionStatus: action.payload };
    case 'SET_ERROR':        return { ...state, extractionError: action.payload };
    case 'SET_EXPORT_PREVIEW':
      return {
        ...state,
        ...(action.payload.open
          ? {
              exportPreviewOpen: true,
              exportPreviewFormat: action.payload.format,
              exportPreviewFilename: action.payload.filename,
              exportPreviewContent: action.payload.content,
            }
          : {
              exportPreviewOpen: false,
              exportPreviewFormat: state.exportPreviewFormat,
              exportPreviewFilename: '',
              exportPreviewContent: '',
            }),
      };
    case 'TOGGLE_REPO_SECTION': return { ...state, repoSectionExpanded: !state.repoSectionExpanded };
    case 'SET_REPO_EXPANDED':return { ...state, repoSectionExpanded: action.payload };
    default: return state;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

const CodeArchitectureViewerInner: React.FC = () => {
  const [archState, archDispatch] = useReducer(archReducer, {
    architecture: null, loading: true, error: null,
  });
  const { architecture, loading, error } = archState;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();

  const [filterState, filterDispatch] = useReducer(filterReducer, {
    selectedLevel: 'context_level',
    selectedEntityTypes: [],
    selectedRelationshipTypes: [],
    showExternal: true,
    graphViewMode: 'developer',
    dependencyViewFilter: 'business',
    searchTerm: '',
    relationshipTypes: [],
  });
  const {
    selectedLevel, selectedEntityTypes, selectedRelationshipTypes,
    showExternal, graphViewMode, dependencyViewFilter, searchTerm, relationshipTypes,
  } = filterState;

  const [selState, selDispatch] = useReducer(selectionReducer, {
    selectedNode: null, selectedEdge: null,
    nodeDescription: '', edgeDescription: '',
    isNodeLoading: false, isEdgeLoading: false,
  });
  const {
    selectedNode, selectedEdge,
    nodeDescription, edgeDescription,
    isNodeLoading, isEdgeLoading,
  } = selState;

  const [exState, exDispatch] = useReducer(extractionReducer, {
    githubUrl: '', isExtracting: false,
    extractionStatus: null, extractionError: null,
    repoSectionExpanded: true,
    localPath: '',
    exportPreviewOpen: false,
    exportPreviewFormat: 'mermaid',
    exportPreviewFilename: '',
    exportPreviewContent: '',
  });
  const {
    githubUrl,
    localPath,
    isExtracting,
    extractionStatus,
    extractionError,
    repoSectionExpanded,
    exportPreviewOpen,
    exportPreviewFormat,
    exportPreviewFilename,
    exportPreviewContent,
  } = exState;

  const [ctxReviewState, ctxReviewDispatch] = useReducer(contextReviewReducer, {
    open: false,
    taskId: null,
    repoKey: null,
    pendingResults: null,
    initialPayload: null,
    submitting: false,
    error: null,
  });

  const pollIntervalRef = useRef<number | null>(null);

  // ── Shim setters (keep child prop interfaces unchanged) ───────────────────
  const setArchitecture = (v: C4Architecture | null) =>
    archDispatch({ type: 'SET_ARCHITECTURE', payload: v });
  const setLoading = (v: boolean) => archDispatch({ type: 'SET_LOADING', payload: v });
  const setError = (v: string | null) => archDispatch({ type: 'SET_ERROR', payload: v });

  const setSelectedLevel = (v: string) => filterDispatch({ type: 'SET_LEVEL', payload: v });
  const setSelectedEntityTypes = (v: string[]) =>
    filterDispatch({ type: 'SET_ENTITY_TYPES', payload: v });
  const setSelectedRelationshipTypes = (v: string[]) =>
    filterDispatch({ type: 'SET_RELATIONSHIP_TYPES', payload: v });
  const setShowExternal = (v: boolean) =>
    filterDispatch({ type: 'SET_SHOW_EXTERNAL', payload: v });
  const setGraphViewMode = (v: 'developer' | 'executive') =>
    filterDispatch({ type: 'SET_VIEW_MODE', payload: v });
  const setDependencyViewFilter = (v: 'all' | 'business' | 'technical') =>
    filterDispatch({ type: 'SET_DEPENDENCY_VIEW', payload: v });
  const setSearchTerm = (v: string) =>
    filterDispatch({ type: 'SET_SEARCH_TERM', payload: v });
  const setRelationshipTypes = (v: string[]) =>
    filterDispatch({ type: 'SET_REL_TYPE_LIST', payload: v });

  const setSelectedNode = (node: any) => {
    if (node === null) {
      selDispatch({ type: 'CLEAR_NODE' });
    } else {
      selDispatch({ type: 'SELECT_NODE', node, description: '' });
    }
  };
  const setSelectedEdge = (edge: any) => {
    if (edge === null) {
      selDispatch({ type: 'CLEAR_EDGE' });
    } else {
      selDispatch({ type: 'SELECT_EDGE', edge });
    }
  };
  const setNodeDescription = (v: string) =>
    selDispatch({ type: 'SET_NODE_DESCRIPTION', payload: v });
  const setEdgeDescription = (v: string) =>
    selDispatch({ type: 'SET_EDGE_DESCRIPTION', payload: v });
  const setIsNodeLoading = (_v: boolean) => { /* handled by SELECT_NODE/CLEAR_NODE */ };
  const setIsEdgeLoading = (v: boolean) =>
    selDispatch({ type: 'SET_EDGE_LOADING', payload: v });

  const setGithubUrl = (v: string) => exDispatch({ type: 'SET_URL', payload: v });
  const setLocalPath = (v: string) => exDispatch({ type: 'SET_LOCAL_PATH', payload: v });
  const setIsExtracting = (v: boolean) => exDispatch({ type: 'SET_EXTRACTING', payload: v });
  const setExtractionStatus = (v: string | null) => exDispatch({ type: 'SET_STATUS', payload: v });
  const setExtractionError = (v: string | null) => exDispatch({ type: 'SET_ERROR', payload: v });
  const setExportPreview = (v: {
    open: boolean;
    format: 'structurizr' | 'mermaid';
    filename: string;
    content: string;
  }) => exDispatch({ type: 'SET_EXPORT_PREVIEW', payload: v });
  const setRepoSectionExpanded = (v: boolean) =>
    exDispatch({ type: 'SET_REPO_EXPANDED', payload: v });

  const applyArchitecture = useCallback((data: any) => {
    // Ensure c4_model_version exists (API might not include it)
    if (!data.c4_model_version) {
      data.c4_model_version = '1.0';
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
          compliance_confidence: data.system_context?.compliance_confidence,
          compliance_factors: data.system_context?.compliance_factors,
          purpose: data.system_context?.purpose || data.system_context?.description,
          description: data.system_context?.description || data.system_context?.purpose,
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
          entity_type: actor.type || 'person',
          language: 'Unknown',
          file_path: '',
          attributes: {
            description: actor.description || actor.role || '',
            role: actor.role || actor.type || 'person',
          },
        })
      );

      // Types that map to TECHNICAL_INFRA when dependency_type is not set
      const TECH_INFRA_DEP_TYPES = new Set([
        'database', 'cache', 'logging', 'documentation', 'queue',
      ]);
      const inferDepType = (dep: any): { dep_type: string; dep_confidence: number } => {
        if (dep.dependency_type && dep.dependency_type !== 'UNKNOWN') {
          return { dep_type: dep.dependency_type, dep_confidence: dep.classification_confidence ?? 0.5 };
        }
        if (TECH_INFRA_DEP_TYPES.has(dep.type)) {
          return { dep_type: 'TECHNICAL_INFRA', dep_confidence: 0.85 };
        }
        if (dep.type === 'external_service' || dep.type === 'external_system') {
          return { dep_type: 'BUSINESS_SYSTEM', dep_confidence: 0.6 };
        }
        return { dep_type: 'UNKNOWN', dep_confidence: 0.5 };
      };

      const deriveExternalDisplayName = (dep: any, index: number) => {
        const rawName = String(dep.name || '').trim();
        if (rawName && !/^:?\d{2,5}$/.test(rawName)) {
          return rawName;
        }

        const detectedFrom = String(dep.detected_from || '');
        const serviceMatch = detectedFrom.match(/([A-Za-z0-9_.-]+)\/Dockerfile/i);
        if (serviceMatch?.[1]) {
          return serviceMatch[1].replace(/\./g, '-');
        }

        return rawName || dep.url || `External ${index + 1}`;
      };

      const isInternalDockerDependency = (dep: any) => {
        const detectedFrom = String(dep.detected_from || '').toLowerCase();
        const depName = String(dep.name || '').toLowerCase();
        const depUrl = String(dep.url || '').toLowerCase();
        const depType = String(dep.type || '').toLowerCase();

        const isLocalUrl =
          depUrl.startsWith('http://localhost') ||
          depUrl.startsWith('https://localhost') ||
          depUrl.startsWith('http://127.0.0.1') ||
          depUrl.startsWith('https://127.0.0.1') ||
          depUrl.startsWith('http://0.0.0.0');

        const hasNoPublicUrl = depUrl === '' || isLocalUrl;

        const looksDockerDerived =
          /dockerfile|docker-compose|compose\.ya?ml|containers?\//.test(
            detectedFrom
          ) || depType === 'container';

        const looksInternalServiceName =
          /^:?\d{2,5}$/.test(depName) ||
          /(^|[._/-])(cms|wps|service|api|menu|products|pages|translations|milestones|tenants)([._/-]|$)/.test(
            depName
          ) ||
          /\/(cms|wps)[^/]*\/dockerfile/.test(detectedFrom);

        return hasNoPublicUrl && looksDockerDerived && looksInternalServiceName;
      };

      const externalEntities = (data.system_context?.external_dependencies || [])
        .filter((dep: any) => !isInternalDockerDependency(dep))
        .map((dep: any, idx: number) => {
          const { dep_type, dep_confidence } = inferDepType(dep);
          return {
            id: `context_external_${idx}`,
            name: deriveExternalDisplayName(dep, idx),
            entity_type: dep.type || 'external_system',
            language: 'Unknown',
            file_path: dep.detected_from || '',
            attributes: {
              url: dep.url,
              detected_from: dep.detected_from,
              is_external: true,
              protocol: dep.protocol,
              dependency_type: dep_type,
              classification_confidence: dep_confidence,
              classification_reasoning: dep.classification_reasoning || '',
            },
          };
        });

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
                attributes: { description: rel.description, protocol: (rel as any).protocol },
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
        compliance_confidence: sysCtxForComponents.compliance_confidence,
        compliance_factors: sysCtxForComponents.compliance_factors,
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

  const handleCloseContextReview = useCallback(() => {
    const pending = ctxReviewState.pendingResults;
    ctxReviewDispatch({ type: 'CLOSE' });
    if (pending) {
      applyArchitecture(pending);
      setSelectedLevel('context_level');
    }
  }, [ctxReviewState.pendingResults, applyArchitecture]);

  const handleSubmitContextReview = useCallback(
    async (payload: ContextFeedbackPayload) => {
      const taskId = ctxReviewState.taskId;
      const repoKey = ctxReviewState.repoKey;
      if (!taskId || !repoKey) {
        handleCloseContextReview();
        return;
      }

      ctxReviewDispatch({ type: 'SET_ERROR', payload: null });
      ctxReviewDispatch({ type: 'SET_SUBMITTING', payload: true });
      persistStoredContextFeedback(repoKey, payload);

      try {
        const updated = await codeArchitectureAPI.submitContextFeedback(
          taskId,
          payload
        );
        ctxReviewDispatch({ type: 'SET_SUBMITTING', payload: false });
        ctxReviewDispatch({ type: 'CLOSE' });
        if (updated) {
          applyArchitecture(updated);
          setSelectedLevel('context_level');
        }
      } catch (e) {
        const msg =
          e instanceof Error ? e.message : 'Failed to apply context feedback';
        ctxReviewDispatch({ type: 'SET_SUBMITTING', payload: false });
        ctxReviewDispatch({ type: 'SET_ERROR', payload: msg });
      }
    },
    [ctxReviewState.taskId, ctxReviewState.repoKey, applyArchitecture, handleCloseContextReview]
  );

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
              const repoKey = makeContextFeedbackRepoKey(githubUrl.trim(), '');
              if (needsHumanContextReview(results)) {
                const payload = buildInitialContextFeedbackPayload(results, repoKey);
                ctxReviewDispatch({
                  type: 'OPEN',
                  taskId,
                  repoKey,
                  results,
                  payload,
                });
              } else {
                applyArchitecture(results);
                setSelectedLevel('context_level');
              }
            }
          } else if (status.status === 'failed') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionError(status.message || 'Extraction failed');
          }
        } catch {
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
  }, [githubUrl, applyArchitecture, ctxReviewDispatch]);

  // Local folder scan handler
  const handleScanLocalPath = useCallback(async () => {
    const path = localPath.trim();
    if (!path) {
      setExtractionError('Please enter a local folder path (e.g. /cms)');
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
        throw new Error('No task id returned from scan');
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
            setExtractionStatus('Scan completed');

            const results = await codeArchitectureAPI.getExtractionResults(taskId);
            if (results) {
              const repoKey = makeContextFeedbackRepoKey('', localPath.trim());
              if (needsHumanContextReview(results)) {
                const payload = buildInitialContextFeedbackPayload(results, repoKey);
                ctxReviewDispatch({
                  type: 'OPEN',
                  taskId,
                  repoKey,
                  results,
                  payload,
                });
              } else {
                applyArchitecture(results);
                setSelectedLevel('context_level');
              }
            }
          } else if (status.status === 'failed') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsExtracting(false);
            setExtractionError(status.message || 'Scan failed');
          }
        } catch {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsExtracting(false);
          setExtractionError('Failed to poll scan status');
        }
      }, 2000);
    } catch (err) {
      setIsExtracting(false);
      setExtractionError(
        err instanceof Error ? err.message : 'Failed to start scan'
      );
    }
  }, [localPath, applyArchitecture, ctxReviewDispatch]);

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
          } catch {
            clearInterval(pollInterval);
            setIsExtracting(false);
            setExtractionError('Failed to poll extraction status');
          }
        }, 3000); // Poll every 3 seconds for batch operations
      } catch (err) {
        setIsExtracting(false);
        let errorMessage = 'Failed to scan GitHub organization';
        
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
              errorMessage = 'Request timed out. Try reducing max repositories or try again.';
            } else {
              errorMessage = detail || `Server error (${status})`;
            }
          } else if (err.code === 'ECONNABORTED') {
            errorMessage = 'Request timed out. GitHub API may be slow. Try again with fewer repositories.';
          } else if (err.message) {
            errorMessage = err.message;
          }
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        
        setExtractionError(errorMessage);
      }
    },
    [applyArchitecture]
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
          ...levelData.entities.map(e => ({ ...e, level: selectedLevel }))
        );
      }
      if (levelData.relationships) {
        allRelationships.push(...levelData.relationships);
      }
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
      const sc = architecture.system_context;
      const systemName = sc?.name || 'System';
      allEntities.push({
        id: `context_system_${systemName}`,
        name: systemName,
        entity_type: 'system',
        language: 'Unknown',
        file_path: '',
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
      
      // NEW: Dependency type filter for C4 Context level
      let dependencyTypeMatch = true;
      if (selectedLevel === 'context_level' && e.attributes?.is_external) {
        // Drop docker/compose-derived "externals" (they belong to container level).
        if (isDockerDerivedContextExternal(e)) {
          return false;
        }

        const depType = e.attributes?.dependency_type;
        if (dependencyViewFilter === 'business') {
          dependencyTypeMatch = depType === 'BUSINESS_SYSTEM';
        } else if (dependencyViewFilter === 'technical') {
          dependencyTypeMatch = depType === 'TECHNICAL_INFRA';
        }
        // 'all' shows everything
      }

      return typeMatch && externalMatch && searchMatch && dependencyTypeMatch;
    });

    // Filter relationships by selected relationship types first
    const relationshipTypeFiltered = allRelationships.filter(r => {
      const typeMatch =
        selectedRelationshipTypes.length === 0 ||
        selectedRelationshipTypes.includes(r.relationship_type);
      return typeMatch;
    });

    let collapsedRelationships: CodeRelationship[] | null = null;

    // Executive view: collapse technical infra externals into one boundary node
    if (selectedLevel === 'context_level' && graphViewMode === 'executive') {
      const technicalEntities = filteredEntities.filter(
        entity => entity.attributes?.is_external && isTechnicalContextEntity(entity)
      );
      if (technicalEntities.length > 0) {
        const platformNodeId = 'context_platform_services';
        const platformNode: CodeEntity = {
          id: platformNodeId,
          name: 'Platform Services',
          entity_type: 'external_system',
          language: 'Unknown',
          file_path: '',
          attributes: {
            is_external: true,
            platform_boundary: true,
            dependency_type: 'TECHNICAL_INFRA',
            collapsed_count: technicalEntities.length,
            collapsed_services: technicalEntities.map(entity => entity.name).slice(0, 20),
          },
          level: selectedLevel,
        };

        const technicalIds = new Set(technicalEntities.map(entity => entity.id));
        filteredEntities = filteredEntities.filter(
          entity => !technicalIds.has(entity.id)
        );
        filteredEntities.push(platformNode);

        const originalEntityIds = new Set([
          ...filteredEntities.map(entity => entity.id),
          ...technicalIds,
        ]);

        const remap = new Map<string, string>();
        technicalIds.forEach(id => remap.set(id, platformNodeId));

        const deduped = new Map<string, CodeRelationship>();
        relationshipTypeFiltered.forEach(rel => {
          if (!rel.target_entity_id) return;
          if (!originalEntityIds.has(rel.source_entity_id)) return;
          if (!originalEntityIds.has(rel.target_entity_id)) return;

          const source = remap.get(rel.source_entity_id) || rel.source_entity_id;
          const target = remap.get(rel.target_entity_id) || rel.target_entity_id;
          if (source === target) return;

          const key = `${source}|${target}|${rel.relationship_type}`;
          if (!deduped.has(key)) {
            deduped.set(key, {
              ...rel,
              source_entity_id: source,
              target_entity_id: target,
            });
          }
        });
        collapsedRelationships = Array.from(deduped.values());
      }
    }

    // Create entity lookup
    const entityIds = new Set(filteredEntities.map(e => e.id));

    // Filter relationships by visible entity IDs (and use executive collapsed set if available)
    const filteredRelationships: CodeRelationship[] =
      (collapsedRelationships || relationshipTypeFiltered).filter(r => {
        const validSource = entityIds.has(r.source_entity_id);
        const validTarget = r.target_entity_id && entityIds.has(r.target_entity_id);
        return validSource && validTarget;
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
          ...(e.entity_type === 'system' ? { style: { width: 230, minHeight: 80 } } : {}),
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
              runtime_info: containerInfo.runtime_info,
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

    const isContextLevel = selectedLevel === 'context_level';
    const entityById = new Map(filteredEntities.map(entity => [entity.id, entity]));
    const rfEdges: Edge[] = filteredRelationships
      .filter(r => r.target_entity_id)
      .map((r, idx) => {
        const sourceEntity = entityById.get(r.source_entity_id);
        const targetEntity = r.target_entity_id
          ? entityById.get(r.target_entity_id)
          : undefined;
        const businessCopy = buildBusinessRelationshipCopy(
          r.relationship_type,
          r.attributes?.description,
          sourceEntity?.name,
          targetEntity?.name,
          sourceEntity?.entity_type,
          targetEntity?.entity_type
        );

        return {
          id: `edge-${idx}`,
          source: r.source_entity_id,
          target: r.target_entity_id!,
          type: isContextLevel ? 'C4Edge' : 'smoothstep',
          animated: false,
          interactionWidth: 16,
          label: isContextLevel ? businessCopy.label : undefined,
          style: {
            stroke: isContextLevel ? '#1168bd' : '#b0bec5',
            strokeWidth: isContextLevel ? 2.8 : 2,
          },
          data: {
            description:
              isContextLevel && businessCopy.sentence
                ? businessCopy.sentence
                : r.attributes?.description,
            protocol: r.attributes?.protocol,
            relationship_type: r.relationship_type,
            business_label: businessCopy.label,
            source_label: sourceEntity?.name,
            target_label: targetEntity?.name,
          },
        };
      });

    const dependencyEdges =
      selectedLevel === 'container_level' && filteredRelationships.length === 0
        ? generateC4Edges(
            architecture?.containers || [],
            architecture?.relationships?.containers || []
          )
        : [];

    const mergedEdges = [...rfEdges, ...dependencyEdges];

    // Apply layout — use star layout for C4 context level, dagre for everything else
    let layoutedNodes: Node[];
    let layoutedEdges: Edge[];
    if (selectedLevel === 'context_level') {
      layoutedNodes = layoutContextLevel([...rfNodes], graphViewMode);
      layoutedEdges = mergedEdges;
    } else {
      const nodesForLayout =
        selectedLevel === 'container_level' && graphViewMode === 'executive'
          ? applyExecutiveContainerGrouping(rfNodes)
          : rfNodes;
      const result = getLayoutedElements(nodesForLayout, mergedEdges);
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

    const elevatedNodes = nodesWithValidPositions.map(node => ({
      ...node,
      zIndex: 10,
    }));

    // No group frames — use clean individual-node C4 layout (like image 2)
    const finalNodes = elevatedNodes;

    setNodes(finalNodes);
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
    graphViewMode,
    dependencyViewFilter,
    searchTerm,
    fitView,
  ]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedEdge(null);
    setEdgeDescription('');
    setSelectedNode(node.data);
    
    // All descriptions must be precomputed - no LLM calls
    const precomputedDescription =
      node.data?.containerMeta?.llm_description ||
      node.data?.containerMeta?.description ||
      node.data?.llm_description ||
      node.data?.attributes?.llm_description ||
      node.data?.attributes?.description ||
      node.data?.attributes?.purpose;

    setNodeDescription(normalizeDescription(precomputedDescription) || '');
    setIsNodeLoading(false);
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
    } catch {
      setEdgeDescription('Unable to generate description right now.');
    } finally {
      setIsEdgeLoading(false);
    }
  }, []);

  const avgConnections =
    nodes.length > 0 ? (edges.length / nodes.length).toFixed(1) : '0';

  const downloadTextFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const handleExportStructurizr = async () => {
    try {
      const payload = await codeArchitectureAPI.exportStructurizr();
      setExportPreview({
        open: true,
        format: 'structurizr',
        filename: payload.filename,
        content: payload.content,
      });
      setExtractionStatus('Structurizr export ready');
      setExtractionError(null);
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : 'Failed to export Structurizr DSL';
      setExtractionError(msg);
    }
  };

  const handleExportMermaid = async () => {
    try {
      const payload = await codeArchitectureAPI.exportMermaid();
      setExportPreview({
        open: true,
        format: 'mermaid',
        filename: payload.filename,
        content: payload.content,
      });
      setExtractionStatus('Mermaid export ready');
      setExtractionError(null);
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : 'Failed to export Mermaid snippet';
      setExtractionError(msg);
    }
  };

  const toggleLevel = (level: string) => {
    setSelectedLevel(level);
  };

  const toggleRelationshipType = (type: string) => {
    const next = selectedRelationshipTypes.includes(type)
      ? selectedRelationshipTypes.filter(t => t !== type)
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
            Run extraction above or execute{' '}
            <code>python -m services.code_extraction.c4_extractor</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="code-architecture-viewer">
      <ExportPreviewDialog
        open={exportPreviewOpen}
        format={exportPreviewFormat}
        filename={exportPreviewFilename}
        content={exportPreviewContent}
        onClose={() =>
          setExportPreview({
            open: false,
            format: exportPreviewFormat,
            filename: '',
            content: '',
          })
        }
        onDownload={() =>
          downloadTextFile(exportPreviewFilename, exportPreviewContent)
        }
      />
      {ctxReviewState.open && ctxReviewState.initialPayload ? (
        <ContextReviewDialog
          open={ctxReviewState.open}
          title="System Context Review"
          submitting={ctxReviewState.submitting}
          error={ctxReviewState.error}
          initial={ctxReviewState.initialPayload}
          onCancel={handleCloseContextReview}
          onSubmit={handleSubmitContextReview}
        />
      ) : null}
      <ArchitectureHeader
        nodeCount={nodes.length}
        edgeCount={edges.length}
        avgConnections={avgConnections}
        onExportStructurizr={handleExportStructurizr}
        onExportMermaid={handleExportMermaid}
      />

      <div className="viewer-layout">
        <FiltersSidebar
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          selectedLevel={selectedLevel}
          toggleLevel={toggleLevel}
          relationshipTypes={relationshipTypes}
          selectedRelationshipTypes={selectedRelationshipTypes}
          toggleRelationshipType={toggleRelationshipType}
          showExternal={showExternal}
          setShowExternal={setShowExternal}
          graphViewMode={graphViewMode}
          setGraphViewMode={setGraphViewMode}
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

        <div className="graph-main">
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
            isLoading={isExtracting}
            loadingText={extractionStatus}
          />

          {selectedNode && (
            <div className="node-inspector-overlay">
              <NodeDetailsPanel
                selectedNode={selectedNode}
                onClose={() => setSelectedNode(null)}
                nodeDescription={nodeDescription}
                isNodeLoading={isNodeLoading}
                variant="overlay"
                showClose={true}
              />
            </div>
          )}

          {selectedEdge && !selectedNode && (
            <div className="node-inspector-overlay">
              <EdgeDetailsPanel
                selectedEdge={selectedEdge}
                onClose={() => setSelectedEdge(null)}
                edgeDescription={edgeDescription}
                isEdgeLoading={isEdgeLoading}
                variant="overlay"
                showClose={true}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CodeArchitectureViewer;
