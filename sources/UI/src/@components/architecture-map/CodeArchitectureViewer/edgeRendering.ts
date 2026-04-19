import type { Edge } from "reactflow";

/**
 * Relationship shape required to build graph edges in the architecture viewer.
 */
export interface GraphRelationship {
  source_entity_id: string;
  target_entity_id: string | null;
  relationship_type: string;
  attributes?: {
    description?: string;
    protocol?: string;
    [key: string]: unknown;
  };
}

/**
 * Minimal entity shape used to derive edge presentation metadata.
 */
export interface GraphEntity {
  id: string;
  name: string;
  entity_type?: string;
}

/**
 * Label placement options for custom C4 edge annotations.
 */
export type EdgeLabelPlacement = "source" | "target" | "center";

/**
 * Maximum number of words shown in a compact graph label.
 */
const MAX_GRAPH_LABEL_WORDS = 6;

/**
 * Maximum number of characters shown in a compact graph label.
 */
const MAX_GRAPH_LABEL_CHARS = 42;

const normalizeEdgeText = (value?: unknown) => {
  if (typeof value !== "string") {
    return undefined;
  }

  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || undefined;
};

/**
 * Normalize entity types to a predictable lowercase value.
 */
const normalizeEntityType = (value?: string) =>
  typeof value === "string" ? value.trim().toLowerCase() : undefined;

/**
 * Turn a relationship type into a compact human label.
 */
const humanizeRelationshipType = (value: string) =>
  value.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

/**
 * Shorten a business sentence so the graph keeps a readable, compact edge label.
 */
const compactContextEdgeLabel = (value?: string) => {
  const normalized = normalizeEdgeText(value);

  if (!normalized) {
    return undefined;
  }

  let compact = normalized.replace(/[.?!]+$/g, "");
  compact = compact.replace(/^(may|can|could|should|would|might)\s+/i, "");

  const connectorMatch = compact.match(
    /\s(?:through|via|using|with|to|for|from|into)\s/i,
  );
  if (connectorMatch?.index) {
    compact = compact.slice(0, connectorMatch.index);
  }

  const wordCount = compact.split(/\s+/).filter(Boolean).length;
  if (wordCount > MAX_GRAPH_LABEL_WORDS) {
    const conjunctionMatch = compact.match(/\s(?:and|but|while)\s/i);
    if (conjunctionMatch?.index) {
      compact = compact.slice(0, conjunctionMatch.index);
    }
  }

  const words = compact.split(/\s+/).filter(Boolean);
  if (words.length > MAX_GRAPH_LABEL_WORDS) {
    compact = words.slice(0, MAX_GRAPH_LABEL_WORDS).join(" ");
  }

  if (compact.length > MAX_GRAPH_LABEL_CHARS) {
    compact = `${compact.slice(0, MAX_GRAPH_LABEL_CHARS - 1).trimEnd()}…`;
  }

  return compact || normalized;
};

/**
 * Derive title and placement metadata for context-level edge labels.
 */
const deriveContextEdgePresentation = (
  relationship: GraphRelationship,
  entitiesById: Map<string, GraphEntity>,
): {
  context_role?: "actor" | "external" | "relationship";
  label_placement: EdgeLabelPlacement;
  label_title?: string;
} => {
  const sourceEntity = entitiesById.get(relationship.source_entity_id);
  const targetEntity = relationship.target_entity_id
    ? entitiesById.get(relationship.target_entity_id)
    : undefined;
  const sourceType = normalizeEntityType(sourceEntity?.entity_type);
  const targetType = normalizeEntityType(targetEntity?.entity_type);
  const isActorToSystem = sourceType === "person" && targetType === "system";
  const isSystemToExternal =
    sourceType === "system" &&
    (targetType === "external_system" || targetType === "external_service");
  const isExternalToSystem =
    (sourceType === "external_system" || sourceType === "external_service") &&
    targetType === "system";

  if (isActorToSystem) {
    return {
      context_role: "actor",
      label_placement: "source",
      label_title: sourceEntity?.name,
    };
  }

  if (isSystemToExternal) {
    return {
      context_role: "external",
      label_placement: "target",
      label_title: targetEntity?.name,
    };
  }

  if (isExternalToSystem) {
    return {
      context_role: "external",
      label_placement: "source",
      label_title: sourceEntity?.name,
    };
  }

  return {
    context_role: "relationship",
    label_placement: "center",
    label_title: humanizeRelationshipType(relationship.relationship_type),
  };
};

/**
 * Build rendered graph edges and suppress protocol labels on context diagrams.
 */
export const buildRenderedEdges = (
  relationships: GraphRelationship[],
  isContextLevel: boolean,
  entities: GraphEntity[] = [],
): Edge[] => {
  const entitiesById = new Map<string, GraphEntity>(
    entities.map((entity) => [entity.id, entity]),
  );

  return relationships
    .filter((relationship) => relationship.target_entity_id)
    .map((relationship, idx) => {
      const description = normalizeEdgeText(
        relationship.attributes?.description,
      );
      const compactLabel = isContextLevel
        ? compactContextEdgeLabel(description)
        : undefined;
      const protocol = isContextLevel
        ? undefined
        : normalizeEdgeText(relationship.attributes?.protocol);
      const contextPresentation = isContextLevel
        ? deriveContextEdgePresentation(relationship, entitiesById)
        : undefined;

      return {
        id: `edge-${idx}`,
        source: relationship.source_entity_id,
        target: relationship.target_entity_id!,
        label: isContextLevel
          ? description || compactLabel || humanizeRelationshipType(relationship.relationship_type)
          : undefined,
        type: isContextLevel ? "C4Edge" : "smoothstep",
        animated: false,
        interactionWidth: 16,
        style: {
          stroke: isContextLevel ? "#1168bd" : "#b0bec5",
          strokeWidth: isContextLevel ? 2.8 : 2,
        },
        data: {
          description,
          graph_label: compactLabel,
          protocol,
          relationship_type: relationship.relationship_type,
          ...contextPresentation,
        },
      };
    });
};
