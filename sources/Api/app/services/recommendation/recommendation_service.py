from typing import Any, Dict, List

import difflib
import logging
import inspect

from app.infrastructure.llm.llm_manager import LLMManager
from app.infrastructure.storage.metadata_store import PostgreSQLMetadataStore
from app.domain.models.recommendations import NodeRecommendation, EdgeRecommendation
from app.services.recommendation.reinforcement_learning_service import (
    ReinforcementLearningService,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self,
        llm_manager: LLMManager,
        metadata_store: PostgreSQLMetadataStore,
        use_reinforcement_learning: bool = True,
    ):
        self.llm_manager = llm_manager
        self.metadata_store = metadata_store
        self.use_reinforcement_learning = use_reinforcement_learning

        if self.use_reinforcement_learning and llm_manager and metadata_store:
            self.rl_service = ReinforcementLearningService(
                llm_manager=llm_manager,
                metadata_store=metadata_store,
                learning_rate=0.1,
                exploration_rate=0.2,
                memory_size=1000,
            )
        else:
            self.rl_service = None

    async def generate_recommendations(
        self,
        task_id: str,
        entities: List[Dict[str, Any]],
        dataset_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            if self.rl_service:
                logger.info(
                    "Generating recommendations using reinforcement learning for task %s",
                    task_id,
                )
                results = await self.rl_service.generate_reinforcement_recommendations(
                    task_id, entities, dataset_profile
                )
            else:
                logger.info(
                    "Generating recommendations using basic LLM approach for task %s",
                    task_id,
                )
                node_recs = await self._generate_node_recommendations(
                    entities, dataset_profile
                )
                edge_recs = await self._generate_edge_recommendations(
                    entities, dataset_profile
                )
                results = {
                    "node_recommendations": node_recs,
                    "edge_recommendations": edge_recs,
                }

            await self._enrich_recommendations(
                results.get("node_recommendations", []),
                results.get("edge_recommendations", []),
                entities,
                dataset_profile,
            )

            return results

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            node_recs = await self._generate_node_recommendations(
                entities, dataset_profile
            )
            edge_recs = await self._generate_edge_recommendations(
                entities, dataset_profile
            )
            results = {
                "node_recommendations": node_recs,
                "edge_recommendations": edge_recs,
            }
            await self._enrich_recommendations(
                results["node_recommendations"],
                results["edge_recommendations"],
                entities,
                dataset_profile,
            )
            return results

    async def process_recommendation_feedback(
        self, task_id: str, feedback_data: Dict[str, Any]
    ) -> None:
        try:
            if self.rl_service:
                logger.info(f"Processing RL feedback for task {task_id}")
                await self.rl_service.process_user_feedback(task_id, feedback_data)
            else:
                logger.info("RL service not available, storing basic feedback")
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            raise

    async def _enrich_recommendations(
        self,
        node_recommendations: List[NodeRecommendation],
        edge_recommendations: List[EdgeRecommendation],
        entities: List[Dict[str, Any]],
        dataset_profile: Dict[str, Any],
    ) -> None:
        if not node_recommendations and not edge_recommendations:
            return

        entity_lookup = {str(entity.get("id")): entity for entity in entities if entity.get("id")}
        entity_values = list(entities)

        dataset_metadata = dataset_profile.get("metadata", {}) or {}
        dataset_summary = {
            "file_path": dataset_profile.get("file_path"),
            "row_count": dataset_profile.get("row_count"),
            "column_count": dataset_profile.get("column_count"),
            "domain": dataset_profile.get("domain")
            or dataset_metadata.get("domain")
            or "unknown",
        }

        column_pool: set[str] = set()
        for entity in entity_values:
            for col in entity.get("source_columns", []) or []:
                column_pool.add(col)

        faiss_neighbors: List[Dict[str, Any]] = []
        if self.metadata_store and column_pool:
            finder = getattr(self.metadata_store, "find_similar_datasets", None)
            if finder:
                try:
                    maybe_result = finder(
                        list(column_pool), dataset_summary.get("domain")
                    )
                    if inspect.isawaitable(maybe_result):
                        faiss_neighbors = await maybe_result
                    else:
                        faiss_neighbors = list(maybe_result or [])
                except Exception as exc:
                    logger.debug("FAISS similarity lookup failed: %s", exc)

        def similarity_score(a: str, b: str) -> float:
            if not a or not b:
                return 0.0
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

        for node in node_recommendations:
            candidates: List[Dict[str, Any]] = []
            for entity in entity_values:
                entity_name = entity.get("name") or ""
                name_score = similarity_score(node.recommended_name, entity_name)
                entity_columns = set(entity.get("source_columns", []) or [])
                node_columns = set(node.source_columns or [])
                total_cols = len(entity_columns.union(node_columns)) or 1
                overlap = len(entity_columns.intersection(node_columns)) / total_cols
                combined_score = max(name_score, overlap)
                if combined_score >= 0.25:
                    candidates.append(
                        {
                            "entity_id": entity.get("id"),
                            "entity_name": entity_name,
                            "entity_type": entity.get("entity_type"),
                            "similarity": round(combined_score, 4),
                            "name_similarity": round(name_score, 4),
                            "column_overlap": round(overlap, 4),
                            "source_columns": list(entity_columns),
                        }
                    )

            candidates.sort(key=lambda c: c["similarity"], reverse=True)

            if not node.source_columns and candidates:
                node.source_columns = candidates[0].get("source_columns", [])

            node.llm_metadata = node.llm_metadata or {}
            node.llm_metadata.setdefault("candidate_entities", candidates[:5])
            node.llm_metadata.setdefault("dataset_context", dataset_summary)
            if faiss_neighbors:
                node.llm_metadata.setdefault(
                    "faiss_neighbors", faiss_neighbors[:5]
                )

        node_candidate_map = {
            str(node.id): node.llm_metadata.get("candidate_entities", [])
            for node in node_recommendations
        }

        for edge in edge_recommendations:
            edge.connection_evidence = edge.connection_evidence or {}

            source_candidates = node_candidate_map.get(str(edge.source_node_id), [])
            target_candidates = node_candidate_map.get(str(edge.target_node_id), [])

            if source_candidates:
                edge.connection_evidence.setdefault(
                    "source_candidates", source_candidates
                )
            if target_candidates:
                edge.connection_evidence.setdefault(
                    "target_candidates", target_candidates
                )

            if faiss_neighbors:
                edge.connection_evidence.setdefault(
                    "faiss_neighbors", faiss_neighbors[:5]
                )

            if dataset_summary:
                edge.connection_evidence.setdefault(
                    "dataset_context", dataset_summary
                )

    async def _generate_node_recommendations(
        self, entities: List[Dict[str, Any]], dataset_profile: Dict[str, Any]
    ) -> List[NodeRecommendation]:
        if not self.llm_manager:
            return []

        prompt = f"""
        Based on the following entities and dataset profile, recommend new nodes to create.

        Entities: {entities}
        Dataset Profile: {dataset_profile}

        Respond with a JSON list of node recommendations.
        Each recommendation should have the following fields:
        - name: The name of the new node
        - entity_type: The type of the new node
        - confidence: The confidence score for this recommendation
        - reasoning: The reasoning behind this recommendation
        """

        try:
            response = await self.llm_manager.generate_text(prompt)
            recommendations = self.llm_manager.parse_json_response(response)
            return [NodeRecommendation(**rec) for rec in recommendations]
        except Exception as e:
            logger.error(f"Failed to generate node recommendations: {e}")
            return []

    async def _generate_edge_recommendations(
        self, entities: List[Dict[str, Any]], dataset_profile: Dict[str, Any]
    ) -> List[EdgeRecommendation]:
        if not self.llm_manager:
            return []

        prompt = f"""
        Based on the following entities and dataset profile, recommend new edges to create.

        Entities: {entities}
        Dataset Profile: {dataset_profile}

        Respond with a JSON list of edge recommendations.
        Each recommendation should have the following fields:
        - source_node_id: The ID of the source node
        - target_node_id: The ID of the target node
        - relationship_type: The type of the relationship
        - confidence: The confidence score for this recommendation
        - reasoning: The reasoning behind this recommendation
        """

        try:
            response = await self.llm_manager.generate_text(prompt)
            recommendations = self.llm_manager.parse_json_response(response)
            return [EdgeRecommendation(**rec) for rec in recommendations]
        except Exception as e:
            logger.error(f"Failed to generate edge recommendations: {e}")
            return []
