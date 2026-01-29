import React, { useCallback, useMemo } from 'react';
import { useState, useEffect } from 'react';
import { ontologyAPI, apiUtils } from '@/services/api';
import { recommendationAPI } from '@/services/recommendationService';
import {
  Database,
  Download,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  FileText,
  AlertCircle,
} from 'lucide-react';
import {
  Entity,
  Relationship,
  PaginationState,
  FeedbackForm,
  FeedbackResponse,
} from '@/types';
import NodeRecommendationList, {
  EnhancedNodeRecommendation,
  NodeSelectionState,
} from '@/@components/recommendation-modal/NodeRecommendations/NodeRecommendationList';
import EdgeRecommendationList, {
  EdgeSelectionState,
  EnhancedEdgeRecommendation,
} from '@/@components/recommendation-modal/EdgeRecommendations/EdgeRecommendationList';
import './OntologyResults.scss';

interface OntologyResultsProps {
  taskId: string;
  onFeedbackSubmitted: (feedback: FeedbackResponse) => void;
  showNotification: (message: string, type: 'success' | 'error' | 'info') => void;
}

const OntologyResults: React.FC<OntologyResultsProps> = ({
  taskId,
  onFeedbackSubmitted,
  showNotification,
}) => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);T

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'entities' | 'relationships'>(
    'entities'
  );
  const [pagination, setPagination] = useState<PaginationState>({
    entities: { page: 1, limit: 20, total: 0 },
    relationships: { page: 1, limit: 20, total: 0 },
  });
  const [feedbackForm, setFeedbackForm] = useState<FeedbackForm>({
    entity_id: undefined,
    relationship_id: undefined,
    feedback_type: 'positive',
    feedback_value: '',
    confidence_delta: 0,
    user_id: 'current_user',
  });
  const [recommendationSession, setRecommendationSession] = useState<{
    node_recommendations: EnhancedNodeRecommendation[];
    edge_recommendations: EnhancedEdgeRecommendation[];
  } | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] =
    useState<boolean>(false);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(
    null
  );
  const [nodeSelections, setNodeSelections] = useState<
    Record<string, NodeSelectionState>
  >({});
  const [edgeSelections, setEdgeSelections] = useState<
    Record<string, EdgeSelectionState>
  >({});
  const [reviewNotes, setReviewNotes] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [currentPhase, setCurrentPhase] = useState<'nodes' | 'edges' | 'completed'>(
    'nodes'
  );
  const [readyForEdges, setReadyForEdges] = useState(false);

  const loadData = useCallback(
    async (type: 'entities' | 'relationships', reset = false) => {
      try {
        setLoading(true);
        setError(null);

        // Use default pagination values, let the component manage its own state
        const page = reset ? 1 : 1;

        let data: any;
        if (type === 'entities') {
          data = await ontologyAPI.getEntities(taskId, 20, (page - 1) * 20);
          if (reset) {
            setEntities(data.items || []);
          } else {
            setEntities(prev => [...prev, ...(data.items || [])]);
          }
        } else {
          data = await ontologyAPI.getRelationships(
            taskId,
            20,
            (page - 1) * 20
          );
          if (reset) {
            setRelationships(data.items || []);
          } else {
            setRelationships(prev => [...prev, ...(data.items || [])]);
          }
        }

        const newPage = reset ? 2 : page + 1;
        setPagination(prev => ({
          ...prev,
          [type]: { page: newPage, limit: 20, total: data.total || 0 },
        }));
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'An unknown error occurred';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [taskId]
  );

  const loadRecommendations = useCallback(async () => {
    if (!taskId) {
      return;
    }

    setRecommendationsLoading(true);
    setRecommendationsError(null);
    setFeedbackMessage(null);

    try {
      const session = await recommendationAPI.getRecommendations(taskId);
      setRecommendationSession(session);

      const nodeState: Record<string, NodeSelectionState> = {};
      session.node_recommendations.forEach(node => {
        nodeState[node.id] = {
          approved: true,
          finalName: node.name,
          entityType: node.entityType,
          confidence: node.confidence ?? 0.75,
          sourceColumns: node.sourceColumns || [],
          metadata: node.metadata || node.llmMetadata || {},
          linkedEntityId: node.linkedEntityId,
        };
      });
      setNodeSelections(nodeState);

      const edgeState: Record<string, EdgeSelectionState> = {};
      session.edge_recommendations.forEach(edge => {
        edgeState[edge.id] = {
          approved: true,
          relationshipType: edge.relationshipType,
          confidence: edge.confidence ?? 0.7,
          metadata: edge.metadata || {},
          reasoning: edge.reasoning,
        };
      });
      setEdgeSelections(edgeState);
      setReviewNotes('');
    } catch (err: unknown) {
      const maybeError = err as { response?: { status?: number }; message?: string };
      if (maybeError?.response?.status === 404) {
        setRecommendationSession(null);
        setNodeSelections({});
        setEdgeSelections({});
        setRecommendationsError('Recommendations are still being generated. Check back shortly.');
      } else {
        setRecommendationsError(
          maybeError?.message || 'Failed to load recommendations'
        );
      }
    } finally {
      setRecommendationsLoading(false);
    }
  }, [taskId]);

  const handleGenerateEdges = useCallback(async () => {
    if (!taskId) return;
    setRecommendationsLoading(true);
    try {
      const session = await recommendationAPI.generateEdgeRecommendations(taskId);
      setRecommendationSession(session);
      setCurrentPhase('edges');
    } catch (err) {
      setRecommendationsError('Failed to generate edge recommendations');
    } finally {
      setRecommendationsLoading(false);
    }
  }, [taskId]);

  const nodeLookup = useMemo(() => {
    const map: Record<string, EnhancedNodeRecommendation> = {};
    recommendationSession?.node_recommendations.forEach(node => {
      map[node.id] = node;
    });
    return map;
  }, [recommendationSession]);

  const edgeLookup = useMemo(() => {
    const map: Record<string, EnhancedEdgeRecommendation> = {};
    recommendationSession?.edge_recommendations.forEach(edge => {
      map[edge.id] = edge;
    });
    return map;
  }, [recommendationSession]);

  const selectedNodeCount = useMemo(
    () =>
      Object.values(nodeSelections).filter(selection => selection?.approved).length,
    [nodeSelections]
  );

  const selectedEdgeCount = useMemo(
    () =>
      Object.values(edgeSelections).filter(selection => selection?.approved).length,
    [edgeSelections]
  );

  const ensureNodeSelection = useCallback(
    (nodeId: string): NodeSelectionState => {
      const existing = nodeSelections[nodeId];
      if (existing) {
        return existing;
      }
      const node = nodeLookup[nodeId];
      return {
        approved: true,
        finalName: node?.name || 'Suggested Node',
        entityType: node?.entityType || 'unknown',
        confidence: node?.confidence ?? 0.75,
        sourceColumns: node?.sourceColumns || [],
        metadata: node?.metadata || node?.llmMetadata || {},
        linkedEntityId: node?.linkedEntityId,
      };
    },
    [nodeSelections, nodeLookup]
  );

  const ensureEdgeSelection = useCallback(
    (edgeId: string): EdgeSelectionState => {
      const existing = edgeSelections[edgeId];
      if (existing) {
        return existing;
      }
      const edge = edgeLookup[edgeId];
      return {
        approved: true,
        relationshipType: edge?.relationshipType || 'RELATED_TO',
        confidence: edge?.confidence ?? 0.7,
        metadata: edge?.metadata || {},
        reasoning: edge?.reasoning,
      };
    },
    [edgeSelections, edgeLookup]
  );

  const handleNodeToggle = useCallback(
    (nodeId: string) => {
      setNodeSelections(prev => {
        const next = { ...prev };
        const selection = ensureNodeSelection(nodeId);
        next[nodeId] = { ...selection, approved: !selection.approved };
        return next;
      });
    },
    [ensureNodeSelection]
  );

  const handleNodeSelectionUpdate = useCallback(
    (nodeId: string, update: Partial<NodeSelectionState>) => {
      setNodeSelections(prev => ({
        ...prev,
        [nodeId]: {
          ...ensureNodeSelection(nodeId),
          ...update,
        },
      }));
    },
    [ensureNodeSelection]
  );

  const handleSelectAllNodes = useCallback(() => {
    setNodeSelections(prev => {
      const updated: Record<string, NodeSelectionState> = { ...prev };
      Object.keys(nodeLookup).forEach(nodeId => {
        updated[nodeId] = { ...ensureNodeSelection(nodeId), approved: true };
      });
      return updated;
    });
  }, [ensureNodeSelection, nodeLookup]);

  const handleDeselectAllNodes = useCallback(() => {
    setNodeSelections(prev => {
      const updated: Record<string, NodeSelectionState> = { ...prev };
      Object.keys(nodeLookup).forEach(nodeId => {
        updated[nodeId] = { ...ensureNodeSelection(nodeId), approved: false };
      });
      return updated;
    });
  }, [ensureNodeSelection, nodeLookup]);

  const handleEdgeToggle = useCallback(
    (edgeId: string) => {
      setEdgeSelections(prev => {
        const next = { ...prev };
        const selection = ensureEdgeSelection(edgeId);
        next[edgeId] = { ...selection, approved: !selection.approved };
        return next;
      });
    },
    [ensureEdgeSelection]
  );

  const handleEdgeSelectionUpdate = useCallback(
    (edgeId: string, update: Partial<EdgeSelectionState>) => {
      setEdgeSelections(prev => ({
        ...prev,
        [edgeId]: {
          ...ensureEdgeSelection(edgeId),
          ...update,
        },
      }));
    },
    [ensureEdgeSelection]
  );

  const handleSelectAllEdges = useCallback(() => {
    setEdgeSelections(prev => {
      const updated: Record<string, EdgeSelectionState> = { ...prev };
      Object.keys(edgeLookup).forEach(edgeId => {
        updated[edgeId] = { ...ensureEdgeSelection(edgeId), approved: true };
      });
      return updated;
    });
  }, [ensureEdgeSelection, edgeLookup]);

  const handleDeselectAllEdges = useCallback(() => {
    setEdgeSelections(prev => {
      const updated: Record<string, EdgeSelectionState> = { ...prev };
      Object.keys(edgeLookup).forEach(edgeId => {
        updated[edgeId] = { ...ensureEdgeSelection(edgeId), approved: false };
      });
      return updated;
    });
  }, [ensureEdgeSelection, edgeLookup]);

  const applySelectedNodesToEntities = useCallback(() => {
    if (!recommendationSession) {
      return;
    }

    const linkedMap = new Map<string, NodeSelectionState>();
    const nodeMap = new Map<string, NodeSelectionState>();
    const nameMap = new Map<string, NodeSelectionState>();

    Object.entries(nodeSelections).forEach(([nodeId, selection]) => {
      if (!selection?.approved) {
        return;
      }
      if (selection.linkedEntityId) {
        linkedMap.set(String(selection.linkedEntityId), selection);
      }
      nodeMap.set(nodeId, selection);
      nameMap.set(selection.finalName.toLowerCase(), selection);
    });

    setEntities(prevEntities =>
      prevEntities.map(entity => {
        const entityId = entity.id ? String(entity.id) : undefined;
        const appliedSelection =
          (entityId && linkedMap.get(entityId)) ||
          (entityId && nodeMap.get(entityId)) ||
          nameMap.get(entity.name.toLowerCase());

        if (!appliedSelection) {
          return entity;
        }

        return {
          ...entity,
          name: appliedSelection.finalName,
          entity_type:
            appliedSelection.entityType || entity.entity_type || 'unknown',
          confidence:
            typeof appliedSelection.confidence === 'number'
              ? appliedSelection.confidence
              : entity.confidence,
          source_columns:
            appliedSelection.sourceColumns?.length
              ? appliedSelection.sourceColumns
              : entity.source_columns,
          attributes: {
            ...(entity.attributes || {}),
            ...(appliedSelection.metadata?.attributes || {}),
          },
        };
      })
    );

    setFeedbackMessage('Applied selected node names to the preview list.');
  }, [nodeSelections, recommendationSession]);

  const applySelectedEdgesToRelationships = useCallback(() => {
    if (!recommendationSession) {
      return;
    }

    const approvedEdges = Object.entries(edgeSelections).filter(
      ([, selection]) => selection?.approved
    );

    if (approvedEdges.length === 0) {
      return;
    }

    setRelationships(prevRelationships => {
      const next = [...prevRelationships];

      approvedEdges.forEach(([edgeId, selection]) => {
        const edgeInfo = edgeLookup[edgeId];
        if (!edgeInfo || !selection) {
          return;
        }

        const updated: Relationship = {
          id: edgeInfo.id,
          relationship_type: selection.relationshipType,
          confidence:
            typeof selection.confidence === 'number'
              ? selection.confidence
              : edgeInfo.confidence ?? 0.7,
          source_entity_id: edgeInfo.sourceNodeId,
          target_entity_id: edgeInfo.targetNodeId,
          attributes: {
            ...(edgeInfo.metadata || {}),
            ...(selection.metadata || {}),
          },
        };

        const existingIndex = next.findIndex(
          relationship => relationship.id === edgeInfo.id
        );

        if (existingIndex >= 0) {
          next[existingIndex] = {
            ...next[existingIndex],
            ...updated,
            attributes: {
              ...(next[existingIndex].attributes || {}),
              ...(updated.attributes || {}),
            },
          };
        } else {
          next.push(updated);
        }
      });

      return next;
    });

    setFeedbackMessage('Applied selected edge recommendations to the preview list.');
  }, [edgeLookup, edgeSelections, recommendationSession]);

  const buildApprovedNodesPayload = useCallback(() => {
    return Object.entries(nodeSelections)
      .filter(([, selection]) => selection?.approved)
      .map(([nodeId, selection]) => {
        const detail = nodeLookup[nodeId];
        return {
          id: nodeId,
          name: selection.finalName,
          entityType: selection.entityType,
          confidence: selection.confidence,
          sourceColumns: selection.sourceColumns,
          linkedEntityId: selection.linkedEntityId,
          metadata: {
            ...(selection.metadata || {}),
            llm_metadata: detail?.llmMetadata ?? detail?.metadata ?? {},
            reasoning: detail?.reasoning,
          },
        };
      });
  }, [nodeSelections, nodeLookup]);

  const buildApprovedEdgesPayload = useCallback(() => {
    return Object.entries(edgeSelections)
      .filter(([, selection]) => selection?.approved)
      .map(([edgeId, selection]) => {
        const detail = edgeLookup[edgeId];
        return {
          id: edgeId,
          relationshipType: selection.relationshipType,
          confidence: selection.confidence,
          metadata: {
            ...(selection.metadata || {}),
            reasoning: selection.reasoning || detail?.reasoning,
          },
          sourceNodeId: detail?.sourceNodeId,
          targetNodeId: detail?.targetNodeId,
        };
      });
  }, [edgeSelections, edgeLookup]);

  const submitRecommendationDecision = useCallback(
    async (approved: boolean) => {
      if (!recommendationSession) {
        return;
      }

      setSubmittingDecision(true);
      setFeedbackMessage(null);

      const payload: Record<string, unknown> = {
        approved,
        notes: reviewNotes || undefined,
      };

      if (approved) {
        payload.items = {
          nodes: buildApprovedNodesPayload(),
          edges: buildApprovedEdgesPayload(),
        };
      }

      try {
        const response = await recommendationAPI.submitRecommendationFeedback(taskId, payload);
        setFeedbackMessage(
          approved
            ? 'Successfully approved recommendations.'
            : 'Recommendations have been rejected.'
        );
        if (response.ready_for_edges) {
          setReadyForEdges(true);
          setCurrentPhase('nodes_completed');
          showNotification('Nodes approved! Generating edge recommendations...', 'info');
        } else {
          showNotification('Feedback submitted successfully!', 'success');
        }
        onFeedbackSubmitted({ success: true, message: 'recommendations-submitted' });
      } catch (err: unknown) {
        const maybeError = err as { message?: string };
        const errorMessage = maybeError?.message || 'Failed to submit recommendation feedback.';
        setFeedbackMessage(errorMessage);
        showNotification(errorMessage, 'error');
      } finally {
        setSubmittingDecision(false);
      }
    },
    [
      recommendationSession,
      reviewNotes,
      buildApprovedNodesPayload,
      buildApprovedEdgesPayload,
      taskId,
      onFeedbackSubmitted,
      showNotification,
    ]
  );

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const feedbackData = {
        type: feedbackForm.feedback_type as 'positive' | 'negative',
        entity_id: feedbackForm.entity_id,
        relationship_id: feedbackForm.relationship_id,
        comment: feedbackForm.feedback_value,
      };

      const result = await ontologyAPI.submitFeedback(feedbackData);

      // Reset form
      setFeedbackForm({
        entity_id: undefined,
        relationship_id: undefined,
        feedback_type: 'positive',
        feedback_value: '',
        confidence_delta: 0,
        user_id: 'current_user',
      });

      // Notify parent component
      onFeedbackSubmitted(result as FeedbackResponse);

      // Refresh data
      loadData(activeTab, true);

      alert('Feedback submitted successfully!');
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to submit feedback: ' + errorMessage);
    }
  };

  const handleExport = async () => {
    try {
      const data = {
        entities,
        relationships,
        taskId,
        exportedAt: new Date().toISOString(),
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ontology-results-${taskId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to export results: ' + errorMessage);
    }
  };

  const loadMore = () => {
    loadData(activeTab);
  };

  useEffect(() => {
    if (
      recommendationsError &&
      recommendationsError.toLowerCase().includes('still being generated')
    ) {
      const timer = setTimeout(() => {
        loadRecommendations();
      }, 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [recommendationsError, loadRecommendations]);

  useEffect(() => {
    if (taskId) {
      loadRecommendations();
    }
  }, [taskId, loadRecommendations]);

  useEffect(() => {
    if (!taskId) return;

    const loadInitialData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load entities
        const entitiesData = await ontologyAPI.getEntities(taskId, 20, 0);
        setEntities(entitiesData.items || []);

        // Load relationships
        const relationshipsData = await ontologyAPI.getRelationships(
          taskId,
          20,
          0
        );
        setRelationships(relationshipsData.items || []);

        // Update pagination
        setPagination({
          entities: { page: 2, limit: 20, total: entitiesData.total || 0 },
          relationships: {
            page: 2,
            limit: 20,
            total: relationshipsData.total || 0,
          },
        });

        await loadRecommendations();
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'An unknown error occurred';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [taskId, loadRecommendations]);

  const handleGenerateRecommendations = useCallback(async () => {
    if (!taskId) return;
    setRecommendationsLoading(true);
    try {
      await recommendationAPI.generateRecommendations(taskId);
      loadRecommendations(); // Reload recommendations after generating them
    } catch (err) {
      setRecommendationsError('Failed to generate recommendations');
    } finally {
      setRecommendationsLoading(false);
    }
  }, [taskId, loadRecommendations]);

  return (
    <div className="ontology-results">
      {/* Header */}
      <div className="results-header">
        <div className="header-info">
          <h2>Extraction Results</h2>
          <p>Task ID: {taskId}</p>
        </div>

        <div className="header-actions">
          <button onClick={handleExport} className="export-button">
            <Download size={16} />
            Export Results
          </button>

          <button
            onClick={() => {
              loadData(activeTab, true);
              loadRecommendations();
            }}
            className="refresh-button"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="results-tabs">
        <button
          className={`tab ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => setActiveTab('entities')}
        >
          <Database size={16} />
          Entities ({entities.length})
        </button>

        <button
          className={`tab ${activeTab === 'relationships' ? 'active' : ''}`}
          onClick={() => setActiveTab('relationships')}
        >
          <FileText size={16} />
          Relationships ({relationships.length})
        </button>
      </div>

      {/* Content */}
      <div className="results-content">
        {error && (
          <div className="error-message">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {activeTab === 'entities' && (
          <div className="entities-section">
            {(recommendationsLoading || recommendationSession || recommendationsError) && (
              <div className="recommendations-panel">
                <div className="recommendations-header">
                  <div>
                    <h3>LLM Node Recommendations</h3>
                    <p className="recommendations-subtitle">
                      Curate suggested node names and apply them directly to the extracted entities.
                    </p>
                  </div>
                  <div className="recommendations-actions">
                    <button
                      className="button-secondary"
                      onClick={handleSelectAllNodes}
                      disabled={!recommendationSession || recommendationsLoading}
                    >
                      Select All
                    </button>
                    <button
                      className="button-secondary"
                      onClick={handleDeselectAllNodes}
                      disabled={!recommendationSession || recommendationsLoading}
                    >
                      Clear
                    </button>
                    <button
                      className="button-muted"
                      onClick={applySelectedNodesToEntities}
                      disabled={!recommendationSession || selectedNodeCount === 0}
                    >
                      Apply Selected Names
                    </button>
                    <button
                      className="button-primary"
                      onClick={() => submitRecommendationDecision(true)}
                      disabled={
                        submittingDecision || !recommendationSession || selectedNodeCount === 0
                      }
                    >
                      <ThumbsUp size={16} /> Approve Selected
                    </button>
                    <button
                      className="button-danger"
                      onClick={() => submitRecommendationDecision(false)}
                      disabled={submittingDecision || !recommendationSession}
                    >
                      <ThumbsDown size={16} /> Reject All
                    </button>
                  </div>
                </div>

                {recommendationsLoading && (
                  <div className="recommendations-status">Loading recommendations...</div>
                )}

                {recommendationsError && (
                  <div className="recommendations-status error">
                    {recommendationsError}
                  </div>
                )}

                {feedbackMessage && (
                  <div className="recommendations-status notice">{feedbackMessage}</div>
                )}

                {recommendationSession && !recommendationsLoading && (
                  <>
                    <div className="recommendations-body">
                      <NodeRecommendationList
                        recommendations={recommendationSession.node_recommendations}
                        selections={nodeSelections}
                        onNodeToggle={handleNodeToggle}
                        onUpdateSelection={handleNodeSelectionUpdate}
                        onSelectAll={handleSelectAllNodes}
                        onDeselectAll={handleDeselectAllNodes}
                      />
                    </div>

                    <div className="review-notes">
                      <label htmlFor="recommendation-notes">
                        Decision notes (optional)
                      </label>
                      <textarea
                        id="recommendation-notes"
                        rows={3}
                        value={reviewNotes}
                        onChange={event => setReviewNotes(event.target.value)}
                        placeholder="Document why you approved or adjusted these recommendations..."
                      />
                    </div>
                    <div className="selection-summary">
                      {selectedNodeCount} of{' '}
                      {recommendationSession.node_recommendations.length} node
                      suggestions selected
                    </div>
                  </>
                )}
              </div>
            )}

          </div>
        )}

        {activeTab === 'relationships' && (
          <div className="relationships-section">
            {(recommendationsLoading ||
              (recommendationSession?.edge_recommendations?.length ?? 0) > 0 ||
              recommendationsError) && (
              <div className="recommendations-panel">
                <div className="recommendations-header">
                  <div>
                    <h3>LLM Relationship Recommendations</h3>
                    <p className="recommendations-subtitle">
                      Review suggested edges between the proposed nodes and incorporate them into the graph.
                    </p>
                  </div>
                  <div className="recommendations-actions">
                    <button
                      className="button-secondary"
                      onClick={handleSelectAllEdges}
                      disabled={!recommendationSession || recommendationsLoading}
                    >
                      Select All
                    </button>
                    <button
                      className="button-secondary"
                      onClick={handleDeselectAllEdges}
                      disabled={!recommendationSession || recommendationsLoading}
                    >
                      Clear
                    </button>
                    <button
                      className="button-muted"
                      onClick={applySelectedEdgesToRelationships}
                      disabled={!recommendationSession || selectedEdgeCount === 0}
                    >
                      Apply Selected Edges
                    </button>
                    <button
                      className="button-primary"
                      onClick={() => submitRecommendationDecision(true)}
                      disabled={
                        submittingDecision || !recommendationSession || selectedEdgeCount === 0
                      }
                    >
                      <ThumbsUp size={16} /> Approve Selected
                    </button>
                    <button
                      className="button-danger"
                      onClick={() => submitRecommendationDecision(false)}
                      disabled={submittingDecision || !recommendationSession}
                    >
                      <ThumbsDown size={16} /> Reject All
                    </button>
                  </div>
                </div>

                {recommendationsLoading && (
                  <div className="recommendations-status">Loading recommendations...</div>
                )}

                {recommendationsError && (
                  <div className="recommendations-status error">
                    {recommendationsError}
                  </div>
                )}

                {feedbackMessage && (
                  <div className="recommendations-status notice">{feedbackMessage}</div>
                )}

                {recommendationSession && !recommendationsLoading && (
                  <>
                    <div className="recommendations-body">
                      <EdgeRecommendationList
                        recommendations={recommendationSession.edge_recommendations}
                        selections={edgeSelections}
                        onEdgeToggle={handleEdgeToggle}
                        onUpdateSelection={handleEdgeSelectionUpdate}
                        onSelectAll={handleSelectAllEdges}
                        onDeselectAll={handleDeselectAllEdges}
                      />
                    </div>
                    <div className="selection-summary">
                      {selectedEdgeCount} of{' '}
                      {recommendationSession.edge_recommendations.length} edge
                      suggestions selected
                    </div>
                  </>
                )}
              </div>
            )}

            <div className="section-header">
              <h3>Discovered Relationships</h3>
              <span className="count">
                {relationships.length} relationships found
              </span>
            </div>

            <div className="relationships-list">
              {relationships.map((relationship, index) => (
                <div
                  key={relationship.id || index}
                  className="relationship-item"
                >
                  <div className="relationship-header">
                    <h4>{relationship.relationship_type}</h4>
                    <div
                      className="confidence-badge"
                      style={{
                        backgroundColor: apiUtils.getConfidenceColor(
                          relationship.confidence
                        ),
                      }}
                    >
                      {apiUtils.formatConfidence(relationship.confidence)}
                    </div>
                  </div>

                  <div className="relationship-details">
                    <div className="detail-item">
                      <strong>From:</strong> {relationship.source_entity_id}
                    </div>
                    <div className="detail-item">
                      <strong>To:</strong> {relationship.target_entity_id}
                    </div>
                    {relationship.source_columns &&
                      relationship.source_columns.length > 0 && (
                        <div className="detail-item">
                          <strong>Source Columns:</strong>{' '}
                          {relationship.source_columns.join(', ')}
                        </div>
                      )}
                    {relationship.attributes &&
                      Object.keys(relationship.attributes).length > 0 && (
                        <div className="detail-item">
                          <strong>Attributes:</strong>
                          <ul className="attributes-list">
                            {Object.entries(relationship.attributes).map(
                              ([key, value]) => (
                                <li key={key}>
                                  <strong>{key}:</strong> {String(value)}
                                </li>
                              )
                            )}
                          </ul>
                        </div>
                      )}
                  </div>

                  <div className="relationship-actions">
                    <button
                      className="feedback-button positive"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          relationship_id: relationship.id,
                        }))
                      }
                    >
                      <ThumbsUp size={16} />
                    </button>

                    <button
                      className="feedback-button negative"
                      onClick={() =>
                        setFeedbackForm(prev => ({
                          ...prev,
                          relationship_id: relationship.id,
                          feedback_type: 'negative',
                        }))
                      }
                    >
                      <ThumbsDown size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Load More Button */}
        {((activeTab === 'entities' &&
          entities.length < pagination.entities.total) ||
          (activeTab === 'relationships' &&
            relationships.length < pagination.relationships.total)) && (
          <div className="load-more-section">
            <button
              onClick={loadMore}
              className="load-more-button"
              disabled={loading}
            >
              {loading ? (
                <RefreshCw className="spinning" size={16} />
              ) : (
                'Load More'
              )}
            </button>
          </div>
        )}
      </div>

      {/* Feedback Form */}
      {(feedbackForm.entity_id || feedbackForm.relationship_id) && (
        <div className="feedback-overlay">
          <div className="feedback-form">
            <h3>Provide Feedback</h3>
            <form onSubmit={handleFeedbackSubmit}>
              <div className="form-group">
                <label>Feedback Type:</label>
                <select
                  value={feedbackForm.feedback_type}
                  onChange={e =>
                    setFeedbackForm(prev => ({
                      ...prev,
                      feedback_type: e.target.value,
                    }))
                  }
                >
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                </select>
              </div>

              <div className="form-group">
                <label>Comments:</label>
                <textarea
                  value={feedbackForm.feedback_value}
                  onChange={e =>
                    setFeedbackForm(prev => ({
                      ...prev,
                      feedback_value: e.target.value,
                    }))
                  }
                  placeholder="Optional feedback comments..."
                />
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  onClick={() =>
                    setFeedbackForm({
                      entity_id: undefined,
                      relationship_id: undefined,
                      feedback_type: 'positive',
                      feedback_value: '',
                      confidence_delta: 0,
                      user_id: 'current_user',
                    })
                  }
                >
                  Cancel
                </button>
                <button type="submit">Submit Feedback</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default OntologyResults;
