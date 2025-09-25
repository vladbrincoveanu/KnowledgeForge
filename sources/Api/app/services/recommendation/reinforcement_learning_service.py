"""
Reinforcement Learning Service for Recommendation Improvement

This service implements reinforcement learning to improve recommendation quality
based on user feedback using the local LLM (GPT via LM Studio).
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

from app.infrastructure.llm.llm_manager import LLMManager
from app.infrastructure.storage.metadata_store import PostgreSQLMetadataStore
from app.domain.models.recommendations import NodeRecommendation, EdgeRecommendation

logger = logging.getLogger(__name__)


@dataclass
class ReinforcementState:
    """Represents the state for RL decision making."""

    entities: List[Dict[str, Any]]
    dataset_profile: Dict[str, Any]
    similar_datasets: List[Dict[str, Any]]
    relationship_patterns: List[Dict[str, Any]]
    previous_feedback: List[Dict[str, Any]]
    context_features: Dict[str, float]


@dataclass
class RLAction:
    """Represents an action in the RL system (a recommendation)."""

    action_type: str  # "node" or "edge"
    recommendation: Dict[str, Any]
    confidence: float
    reasoning: str


@dataclass
class RLFeedback:
    """Represents feedback for learning."""

    action: RLAction
    reward: float  # 1.0 for approved, -1.0 for rejected, 0.5 for modified
    user_modifications: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class ReinforcementLearningService:
    """Service for improving recommendations using reinforcement learning with LLM."""

    def __init__(
        self,
        llm_manager: LLMManager,
        metadata_store: PostgreSQLMetadataStore,
        learning_rate: float = 0.1,
        exploration_rate: float = 0.2,
        memory_size: int = 1000,
    ):
        self.llm_manager = llm_manager
        self.metadata_store = metadata_store
        self.learning_rate = learning_rate
        self.exploration_rate = exploration_rate
        self.memory_size = memory_size

        self.experience_memory: List[RLFeedback] = []

        self.feature_weights = {
            "dataset_similarity": 1.0,
            "pattern_frequency": 0.8,
            "domain_relevance": 0.9,
            "confidence_score": 1.2,
            "historical_success": 1.5,
        }

    async def generate_reinforcement_recommendations(
        self,
        task_id: str,
        entities: List[Dict[str, Any]],
        dataset_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            logger.info(f"Generating RL recommendations for task {task_id}")

            column_patterns = [entity.get("source_columns", []) for entity in entities]
            column_patterns = [col for sublist in column_patterns for col in sublist]
            domain = dataset_profile.get("domain", "unknown")

            similar_datasets = await self.metadata_store.find_similar_datasets(
                column_patterns, domain
            )
            relationship_patterns = await self.metadata_store.get_relationship_patterns(
                [entity.get("entity_type", "") for entity in entities]
            )

            previous_feedback = await self._get_historical_feedback(domain)

            state = ReinforcementState(
                entities=entities,
                dataset_profile=dataset_profile,
                similar_datasets=similar_datasets,
                relationship_patterns=relationship_patterns,
                previous_feedback=previous_feedback,
                context_features=self._extract_context_features(
                    entities, dataset_profile, similar_datasets, relationship_patterns
                ),
            )

            node_actions = await self._generate_node_actions(state)
            edge_actions = await self._generate_edge_actions(state)

            node_recommendations = [
                self._action_to_node_recommendation(action) for action in node_actions
            ]
            edge_recommendations = [
                self._action_to_edge_recommendation(action) for action in edge_actions
            ]

            logger.info(
                "Generated %d node and %d edge recommendations using RL",
                len(node_recommendations),
                len(edge_recommendations),
            )

            return {
                "node_recommendations": node_recommendations,
                "edge_recommendations": edge_recommendations,
                "rl_metadata": {
                    "state_features": state.context_features,
                    "exploration_rate": self.exploration_rate,
                    "similar_datasets_count": len(similar_datasets),
                    "pattern_count": len(relationship_patterns),
                    "faiss_neighbors": similar_datasets[:5],
                },
            }

        except Exception as e:
            logger.error(f"Error in generate_reinforcement_recommendations: {e}")
            raise

    async def process_user_feedback(
        self,
        task_id: str,
        feedback_data: Dict[str, Any],
    ) -> None:
        try:
            logger.info(f"Processing RL feedback for task {task_id}")

            approved_items = feedback_data.get("items", {})
            approved = feedback_data.get("approved", False)

            session = await self.metadata_store.get_recommendation_session(task_id)
            if not session:
                logger.warning(f"No recommendation session found for task {task_id}")
                return

            reward = 1.0 if approved else -1.0

            node_ids = approved_items.get("nodes", [])
            for node_id in node_ids:
                action = RLAction(
                    action_type="node",
                    recommendation={"id": node_id},
                    confidence=0.8,
                    reasoning="User approved",
                )
                feedback = RLFeedback(
                    action=action,
                    reward=reward,
                    user_modifications=feedback_data.get("modifications"),
                )
                self._store_feedback(feedback)

            await self._update_model_weights(session.metadata or {})

            logger.info(
                "Processed feedback for %d nodes and %d edges",
                len(node_ids),
                len(approved_items.get("edges", [])),
            )

        except Exception as e:
            logger.error(f"Error processing RL feedback: {e}")
            raise

    async def _generate_node_actions(self, state: ReinforcementState) -> List[RLAction]:
        actions = []

        try:
            prompt = f"""
            Based on the following context and historical feedback, recommend new nodes to create.
            Use reinforcement learning principles to balance exploration and exploitation.
            
            Current entities: {state.entities[:5]}
            Dataset profile: {state.dataset_profile}
            Similar datasets found: {len(state.similar_datasets)}
            Relationship patterns available: {len(state.relationship_patterns)}
            Historical success rate: {state.context_features.get('historical_success', 0.5)}
            
            Previous feedback patterns:
            {self._summarize_feedback(state.previous_feedback)}
            
            Context features:
            {state.context_features}
            
            Generate 3-5 node recommendations as JSON array. Each should have:
            - name: Node name
            - entity_type: Entity type
            - confidence: Confidence score (0-1)
            - reasoning: Why this recommendation is good
            - exploration_factor: How novel/exploratory this recommendation is (0-1)
            
            Balance between:
            1. Exploiting known successful patterns (high confidence, low exploration)
            2. Exploring new possibilities (lower confidence, high exploration)
            
            Respond only with JSON array.
            """

            response = await self.llm_manager.generate_text(
                prompt, max_tokens=500, temperature=0.7
            )

            if response:
                try:
                    recommendations = self.llm_manager.parse_json_response(response)
                    for rec in recommendations:
                        action = RLAction(
                            action_type="node",
                            recommendation=rec,
                            confidence=rec.get("confidence", 0.5),
                            reasoning=rec.get("reasoning", "LLM generated"),
                        )
                        actions.append(action)
                except Exception as e:
                    logger.error(f"Error parsing node recommendations: {e}")

        except Exception as e:
            logger.error(f"Error generating node actions: {e}")

        return actions

    async def _generate_edge_actions(self, state: ReinforcementState) -> List[RLAction]:
        actions = []

        try:
            entity_types = list(set([e.get("entity_type", "") for e in state.entities]))

            prompt = f"""
            Based on the context and relationship patterns, recommend new edges to create.
            Use reinforcement learning to balance proven patterns with novel connections.
            
            Available entity types: {entity_types}
            Relationship patterns with high success: {state.relationship_patterns[:3]}
            Context features: {state.context_features}
            
            Historical feedback summary:
            {self._summarize_feedback(state.previous_feedback)}
            
            Generate 3-5 edge recommendations as JSON array. Each should have:
            - source_entity_type: Source entity type  
            - target_entity_type: Target entity type
            - relationship_type: Type of relationship
            - confidence: Confidence score (0-1)
            - reasoning: Why this relationship makes sense
            - pattern_match: Whether it matches a known successful pattern
            
            Respond only with JSON array.
            """

            response = await self.llm_manager.generate_text(
                prompt, max_tokens=500, temperature=0.7
            )

            if response:
                try:
                    recommendations = self.llm_manager.parse_json_response(response)
                    for rec in recommendations:
                        action = RLAction(
                            action_type="edge",
                            recommendation=rec,
                            confidence=rec.get("confidence", 0.5),
                            reasoning=rec.get("reasoning", "LLM generated"),
                        )
                        actions.append(action)
                except Exception as e:
                    logger.error(f"Error parsing edge recommendations: {e}")

        except Exception as e:
            logger.error(f"Error generating edge actions: {e}")

        return actions

    def _extract_context_features(
        self,
        entities: List[Dict[str, Any]],
        dataset_profile: Dict[str, Any],
        similar_datasets: List[Dict[str, Any]],
        relationship_patterns: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        features = {}

        if similar_datasets:
            avg_similarity = np.mean(
                [d.get("similarity_score", 0) for d in similar_datasets]
            )
            features["dataset_similarity"] = float(avg_similarity)
        else:
            features["dataset_similarity"] = 0.0

        if relationship_patterns:
            avg_frequency = np.mean(
                [p.get("frequency", 1) for p in relationship_patterns]
            )
            features["pattern_frequency"] = float(avg_frequency)
        else:
            features["pattern_frequency"] = 0.0

        domain = dataset_profile.get("domain", "unknown").lower()
        domain_scores = {
            "finance": 0.9,
            "healthcare": 0.85,
            "retail": 0.8,
            "education": 0.75,
            "unknown": 0.5,
        }
        features["domain_relevance"] = domain_scores.get(domain, 0.5)

        entity_types = set([e.get("entity_type", "") for e in entities])
        features["entity_diversity"] = min(len(entity_types) / 10.0, 1.0)

        features["data_completeness"] = dataset_profile.get("completeness", 0.8)

        return features

    def _action_to_node_recommendation(self, action: RLAction) -> NodeRecommendation:
        rec = action.recommendation
        return NodeRecommendation(
            session_id=uuid.uuid4(),
            recommended_name=rec.get("name", "Generated Node"),
            entity_type=rec.get("entity_type", "unknown"),
            confidence_score=action.confidence,
            reasoning=f"RL Generated: {action.reasoning}",
            source_columns=rec.get("source_columns", []),
            llm_metadata={
                "rl_action": True,
                "exploration_factor": rec.get("exploration_factor", 0.5),
                "generation_method": "reinforcement_learning",
            },
        )

    def _action_to_edge_recommendation(self, action: RLAction) -> EdgeRecommendation:
        rec = action.recommendation
        return EdgeRecommendation(
            session_id=uuid.uuid4(),
            source_node_id=uuid.uuid4(),
            target_node_id=uuid.uuid4(),
            relationship_type=rec.get("relationship_type", "RELATED_TO"),
            confidence_score=action.confidence,
            reasoning=f"RL Generated: {action.reasoning}",
            connection_evidence={
                "pattern_match": rec.get("pattern_match"),
                "action_metadata": {
                    "rl_action": True,
                    "generation_method": "reinforcement_learning",
                },
            },
        )

    async def _get_historical_feedback(self, domain: str) -> List[Dict[str, Any]]:
        try:
            return await self.metadata_store.get_recent_feedback(domain)
        except Exception:
            return []

    def _store_feedback(self, feedback: RLFeedback) -> None:
        self.experience_memory.append(feedback)
        if len(self.experience_memory) > self.memory_size:
            self.experience_memory = self.experience_memory[-self.memory_size :]

    async def _update_model_weights(self, context_metadata: Dict[str, Any]) -> None:
        logger.debug("Updating RL model weights with context metadata: %s", context_metadata)
        # Placeholder: extended RL updates would happen here.
