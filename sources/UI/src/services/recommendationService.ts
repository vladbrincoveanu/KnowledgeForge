import api from './api';

interface NodeRecommendation {
  id: string;
  name: string;
  entityType: string;
  confidence: number;
  reasoning: string;
  sourceColumns?: string[];
  metadata?: Record<string, any>;
  llmMetadata?: Record<string, any>;
  linkedEntityId?: string;
}

interface EdgeRecommendation {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  relationshipType: string;
  confidence: number;
  reasoning: string;
  metadata?: Record<string, any>;
}

interface RecommendationData {
  node_recommendations: NodeRecommendation[];
  edge_recommendations: EdgeRecommendation[];
}

export const recommendationAPI = {
  getRecommendations: async (taskId: string): Promise<RecommendationData> => {
    const response = await api.get(`/v1/extract/${taskId}/recommendations`);
    const session = response.data as any;

    const ensureId = (value?: unknown) => {
      if (value) {
        return String(value);
      }
      if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
        return crypto.randomUUID();
      }
      return `rec-${Math.random().toString(36).slice(2)}`;
    };

    const normalizeNode = (node: any): NodeRecommendation => {
      const llmMetadata = node.llm_metadata || node.metadata || {};
      const sourceColumns =
        node.source_columns || llmMetadata.source_columns || [];
      const candidateEntities = llmMetadata.candidate_entities || [];
      const linkedEntityId =
        node.linked_entity_id ||
        node.linkedEntityId ||
        llmMetadata.human_feedback?.entity_id ||
        candidateEntities?.[0]?.entity_id;

      return {
        id: ensureId(node.id ?? node.session_id),
        name: node.recommended_name ?? node.name ?? 'Suggested Node',
        entityType: node.entity_type ?? node.entityType ?? 'unknown',
        confidence:
          typeof node.confidence_score === 'number'
            ? node.confidence_score
            : typeof node.confidence === 'number'
              ? node.confidence
              : 0,
        reasoning: node.reasoning ?? 'No reasoning provided',
        sourceColumns,
        metadata: llmMetadata,
        llmMetadata,
        linkedEntityId,
      };
    };

    const normalizeEdge = (edge: any): EdgeRecommendation => {
      const metadata = edge.connection_evidence || edge.metadata || {};
      return {
        id: ensureId(edge.id),
        sourceNodeId:
          edge.source_node_id ?? edge.sourceNodeId ?? 'unknown-source',
        targetNodeId:
          edge.target_node_id ?? edge.targetNodeId ?? 'unknown-target',
        relationshipType:
          edge.relationship_type ?? edge.relationshipType ?? 'related_to',
        confidence:
          typeof edge.confidence_score === 'number'
            ? edge.confidence_score
            : typeof edge.confidence === 'number'
              ? edge.confidence
              : 0,
        reasoning: edge.reasoning ?? 'No reasoning provided',
        metadata,
      };
    };

    return {
      node_recommendations: (session?.node_recommendations || []).map(
        normalizeNode
      ),
      edge_recommendations: (session?.edge_recommendations || []).map(
        normalizeEdge
      ),
    };
  },

  submitRecommendationFeedback: async (
    taskId: string,
    feedback: any
  ): Promise<any> => {
    const response = await api.post(
      `/v1/extract/${taskId}/recommendations/feedback`,
      feedback
    );
    return response.data;
  },

  submitFeedback: async (taskId: string, feedback: any): Promise<any> => {
    const response = await api.post(
      `/v1/extract/${taskId}/recommendations/feedback`,
      feedback
    );
    return response.data;
  },

  generateRecommendations: async (taskId: string): Promise<void> => {
    await api.post(`/v1/extract/${taskId}/generate-recommendations`);
  },

  generateEdgeRecommendations: async (
    taskId: string
  ): Promise<RecommendationData> => {
    const response = await api.post(
      `/v1/extract/${taskId}/generate-edge-recommendations`
    );
    return response.data;
  },
};
