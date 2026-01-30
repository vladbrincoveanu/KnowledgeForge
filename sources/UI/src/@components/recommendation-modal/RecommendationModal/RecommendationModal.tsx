import React, { useState, useEffect, useMemo } from 'react';
import NodeRecommendationList, {
  EnhancedNodeRecommendation,
  NodeSelectionState,
} from '../NodeRecommendations/NodeRecommendationList';
import EdgeRecommendationList, {
  EnhancedEdgeRecommendation,
  EdgeSelectionState,
} from '../EdgeRecommendations/EdgeRecommendationList';
import { recommendationAPI } from '@/services/recommendationService';
import './RecommendationModal.scss';

interface RecommendationData {
  node_recommendations: EnhancedNodeRecommendation[];
  edge_recommendations: EnhancedEdgeRecommendation[];
}

interface RecommendationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApprove: (approvedItems: any) => void;
  onReject: () => void;
  taskId: string;
  showNotification: (
    message: string,
    type: 'success' | 'error' | 'info'
  ) => void;
}

const RecommendationModal: React.FC<RecommendationModalProps> = ({
  isOpen,
  onClose,
  onApprove,
  onReject,
  taskId,
  showNotification,
}) => {
  const [recommendations, setRecommendations] =
    useState<RecommendationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [nodeSelections, setNodeSelections] = useState<
    Record<string, NodeSelectionState>
  >({});
  const [edgeSelections, setEdgeSelections] = useState<
    Record<string, EdgeSelectionState>
  >({});
  const [reviewNotes, setReviewNotes] = useState('');
  const [currentPhase, setCurrentPhase] = useState<
    'nodes' | 'edges' | 'completed'
  >('nodes');
  const [readyForEdges, setReadyForEdges] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setNodeSelections({});
      setEdgeSelections({});
      setReviewNotes('');
      recommendationAPI
        .getRecommendations(taskId)
        .then(data => {
          setRecommendations(data);
          setCurrentPhase(data.phase || 'nodes');
          setLoading(false);
          if (data.node_recommendations) {
            const initialNodes: Record<string, NodeSelectionState> = {};
            data.node_recommendations.forEach(node => {
              initialNodes[node.id] = {
                approved: true,
                finalName: node.name,
                entityType: node.entityType,
                confidence: node.confidence ?? 0.75,
                sourceColumns: node.sourceColumns || [],
                metadata: node.metadata || node.llmMetadata || {},
                linkedEntityId: node.linkedEntityId,
              };
            });
            setNodeSelections(initialNodes);
          }
          if (data.edge_recommendations) {
            const initialEdges: Record<string, EdgeSelectionState> = {};
            data.edge_recommendations.forEach(edge => {
              initialEdges[edge.id] = {
                approved: true,
                relationshipType: edge.relationshipType,
                confidence: edge.confidence ?? 0.7,
                metadata: edge.metadata || {},
                reasoning: edge.reasoning,
              };
            });
            setEdgeSelections(initialEdges);
          }
        })
        .catch(error => {
          console.error('Failed to load recommendations:', error);
          setLoading(false);
        });
    }
  }, [isOpen, taskId]);

  const nodeLookup = useMemo(() => {
    const map: Record<string, EnhancedNodeRecommendation> = {};
    recommendations?.node_recommendations.forEach(node => {
      map[node.id] = node;
    });
    return map;
  }, [recommendations]);

  const edgeLookup = useMemo(() => {
    const map: Record<string, EnhancedEdgeRecommendation> = {};
    recommendations?.edge_recommendations.forEach(edge => {
      map[edge.id] = edge;
    });
    return map;
  }, [recommendations]);

  // Selection handling functions
  const handleNodeToggle = (nodeId: string) => {
    setNodeSelections(prev => {
      const current = prev[nodeId];
      return {
        ...prev,
        [nodeId]: {
          ...(current || {
            approved: true,
            finalName: nodeLookup[nodeId]?.name || 'Untitled node',
            entityType: nodeLookup[nodeId]?.entityType || 'unknown',
            confidence: nodeLookup[nodeId]?.confidence || 0.75,
            sourceColumns: nodeLookup[nodeId]?.sourceColumns || [],
            metadata: nodeLookup[nodeId]?.metadata || {},
            linkedEntityId: nodeLookup[nodeId]?.linkedEntityId,
          }),
          approved: !(current?.approved ?? true),
        },
      };
    });
  };

  const handleEdgeToggle = (edgeId: string) => {
    setEdgeSelections(prev => {
      const current = prev[edgeId];
      return {
        ...prev,
        [edgeId]: {
          ...(current || {
            approved: true,
            relationshipType:
              edgeLookup[edgeId]?.relationshipType || 'RELATED_TO',
            confidence: edgeLookup[edgeId]?.confidence || 0.7,
            metadata: edgeLookup[edgeId]?.metadata || {},
            reasoning: edgeLookup[edgeId]?.reasoning,
          }),
          approved: !(current?.approved ?? true),
        },
      };
    });
  };

  const handleSelectAllNodes = () => {
    setNodeSelections(prev => {
      const updated: Record<string, NodeSelectionState> = {};
      Object.entries(prev).forEach(([id, sel]) => {
        updated[id] = { ...sel, approved: true };
      });
      recommendations?.node_recommendations.forEach(node => {
        if (!updated[node.id]) {
          updated[node.id] = {
            approved: true,
            finalName: node.name,
            entityType: node.entityType,
            confidence: node.confidence ?? 0.75,
            sourceColumns: node.sourceColumns || [],
            metadata: node.metadata || node.llmMetadata || {},
            linkedEntityId: node.linkedEntityId,
          };
        }
      });
      return updated;
    });
  };

  const handleDeselectAllNodes = () => {
    setNodeSelections(prev => {
      const updated: Record<string, NodeSelectionState> = {};
      Object.entries(prev).forEach(([id, sel]) => {
        updated[id] = { ...sel, approved: false };
      });
      return updated;
    });
  };

  const handleSelectAllEdges = () => {
    setEdgeSelections(prev => {
      const updated: Record<string, EdgeSelectionState> = {};
      Object.entries(prev).forEach(([id, sel]) => {
        updated[id] = { ...sel, approved: true };
      });
      recommendations?.edge_recommendations.forEach(edge => {
        if (!updated[edge.id]) {
          updated[edge.id] = {
            approved: true,
            relationshipType: edge.relationshipType,
            confidence: edge.confidence ?? 0.7,
            metadata: edge.metadata || {},
            reasoning: edge.reasoning,
          };
        }
      });
      return updated;
    });
  };

  const handleDeselectAllEdges = () => {
    setEdgeSelections(prev => {
      const updated: Record<string, EdgeSelectionState> = {};
      Object.entries(prev).forEach(([id, sel]) => {
        updated[id] = { ...sel, approved: false };
      });
      return updated;
    });
  };

  const handleGenerateEdges = async () => {
    if (!taskId) return;
    setLoading(true);
    try {
      const data = await recommendationAPI.generateEdgeRecommendations(taskId);
      setRecommendations(data);
      setCurrentPhase('edges');
    } catch (err) {
      console.error('Failed to generate edge recommendations:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    const approvedNodes = Object.entries(nodeSelections)
      .filter(([, sel]) => sel?.approved)
      .map(([id, sel]) => {
        const nodeInfo = nodeLookup[id];
        return {
          id,
          name: sel.finalName,
          entityType: sel.entityType,
          confidence: sel.confidence,
          sourceColumns: sel.sourceColumns,
          linkedEntityId: sel.linkedEntityId,
          metadata: {
            ...sel.metadata,
            llm_metadata: nodeInfo?.llmMetadata,
            reasoning: nodeInfo?.reasoning,
          },
        };
      });

    const approvedEdges = Object.entries(edgeSelections)
      .filter(([, sel]) => sel?.approved)
      .map(([id, sel]) => {
        const edgeInfo = edgeLookup[id];
        return {
          id,
          relationshipType: sel.relationshipType,
          confidence: sel.confidence,
          metadata: {
            ...sel.metadata,
            reasoning: sel.reasoning || edgeInfo?.reasoning,
          },
          sourceNodeId: edgeInfo?.sourceNodeId,
          targetNodeId: edgeInfo?.targetNodeId,
        };
      });

    const payload = {
      approved: true,
      notes: reviewNotes,
      items: {
        nodes: approvedNodes,
        edges: approvedEdges,
      },
    };

    try {
      const response = await recommendationAPI.submitFeedback(taskId, payload);
      if (response.ready_for_edges) {
        setReadyForEdges(true);
        setCurrentPhase('nodes_completed');
        showNotification(
          'Nodes approved! Generating edge recommendations...',
          'info'
        );
        // If edge recommendations are already available, switch to edge phase
        if (
          response.edge_recommendations &&
          response.edge_recommendations.length > 0
        ) {
          setRecommendations(prev => ({
            ...prev,
            node_recommendations: prev?.node_recommendations || [],
            edge_recommendations: response.edge_recommendations,
          }));
          setCurrentPhase('edges');
        } else {
          // Otherwise, show loading and poll for edge recommendations
          setLoading(true);
          const interval = setInterval(async () => {
            try {
              const data = await recommendationAPI.getRecommendations(taskId);
              if (
                data.phase === 'edges' &&
                data.edge_recommendations.length > 0
              ) {
                setRecommendations(data);
                setCurrentPhase('edges');
                setLoading(false);
                clearInterval(interval);
                showNotification('Edge recommendations are ready!', 'success');
              }
            } catch (error) {
              console.error('Polling for edge recommendations failed:', error);
              setLoading(false);
              clearInterval(interval);
            }
          }, 3000); // Poll every 3 seconds
        }
      } else {
        onApprove(payload.items);
        showNotification('Feedback submitted successfully!', 'success');
      }
    } catch (error) {
      console.error('Failed to submit recommendation feedback:', error);
      showNotification('Failed to submit feedback. Please try again.', 'error');
    }
  };

  const handleReject = async () => {
    try {
      await recommendationAPI.submitRecommendationFeedback(taskId, {
        approved: false,
        notes: reviewNotes,
      });
      onReject();
      showNotification('Recommendations rejected.', 'info');
    } catch (error) {
      console.error('Failed to reject recommendations:', error);
      showNotification(
        'Failed to reject recommendations. Please try again.',
        'error'
      );
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="recommendation-modal">
      <div className="modal-content">
        <h2>Ontology Recommendations</h2>
        {loading ? (
          <p>Loading recommendations...</p>
        ) : (
          <>
            {recommendations && (
              <>
                {currentPhase === 'nodes' && (
                  <NodeRecommendationList
                    recommendations={recommendations.node_recommendations}
                    selections={nodeSelections}
                    onNodeToggle={handleNodeToggle}
                    onUpdateSelection={(nodeId, update) =>
                      setNodeSelections(prev => ({
                        ...prev,
                        [nodeId]: {
                          ...(prev[nodeId] ?? {
                            approved: true,
                            finalName:
                              nodeLookup[nodeId]?.name || 'Untitled node',
                            entityType:
                              nodeLookup[nodeId]?.entityType || 'unknown',
                            confidence: nodeLookup[nodeId]?.confidence || 0.75,
                            sourceColumns:
                              nodeLookup[nodeId]?.sourceColumns || [],
                            metadata:
                              nodeLookup[nodeId]?.metadata ||
                              nodeLookup[nodeId]?.llmMetadata ||
                              {},
                            linkedEntityId: nodeLookup[nodeId]?.linkedEntityId,
                          }),
                          ...update,
                        },
                      }))
                    }
                    onSelectAll={handleSelectAllNodes}
                    onDeselectAll={handleDeselectAllNodes}
                  />
                )}
                {currentPhase === 'nodes_completed' && (
                  <div className="phase-transition">
                    <p>
                      Nodes approved. Generating relationships, please wait...
                    </p>
                  </div>
                )}
                {currentPhase === 'edges' && (
                  <EdgeRecommendationList
                    recommendations={recommendations.edge_recommendations}
                    selections={edgeSelections}
                    onEdgeToggle={handleEdgeToggle}
                    onUpdateSelection={(edgeId, update) =>
                      setEdgeSelections(prev => ({
                        ...prev,
                        [edgeId]: {
                          ...(prev[edgeId] ?? {
                            approved: true,
                            relationshipType:
                              edgeLookup[edgeId]?.relationshipType ||
                              'RELATED_TO',
                            confidence: edgeLookup[edgeId]?.confidence || 0.7,
                            metadata: edgeLookup[edgeId]?.metadata || {},
                            reasoning: edgeLookup[edgeId]?.reasoning,
                          }),
                          ...update,
                        },
                      }))
                    }
                    nodeLookup={nodeLookup}
                    onSelectAll={() => handleSelectAllEdges(true)}
                    onDeselectAll={() => handleSelectAllEdges(false)}
                  />
                )}
                <div className="review-notes">
                  <label htmlFor="review-notes">
                    Decision notes (optional)
                  </label>
                  <textarea
                    id="review-notes"
                    rows={3}
                    value={reviewNotes}
                    onChange={event => setReviewNotes(event.target.value)}
                    placeholder="Document why you approved or adjusted these recommendations..."
                  />
                </div>
              </>
            )}
            <div className="modal-actions">
              <button onClick={handleReject}>Reject All</button>
              <button onClick={handleApprove}>Approve Selected</button>
              <button onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default RecommendationModal;
