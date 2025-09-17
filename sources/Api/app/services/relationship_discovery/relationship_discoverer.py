"""Relationship discovery module for finding connections between entities."""

import hashlib
import logging
from collections import defaultdict
from typing import Any, Optional
import pandas as pd
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.domain.models.entities import ColumnProfile, DataType, Entity, Relationship
from app.infrastructure.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)


def _safe_config_get(config, key, default=None):
    """Safely get configuration value from either dict or Config object."""
    if hasattr(config, 'get'):
        return config.get(key, default)
    elif hasattr(config, key):
        return getattr(config, key, default)
    elif hasattr(config, 'extraction') and hasattr(config.extraction, key):
        return getattr(config.extraction, key, default)
    else:
        return default


class RelationshipDiscoverer:
    """Discovers relationships between entities in CSV data."""

    def __init__(
        self,
        llm_manager: Optional[LLMManager] = None,
        use_sbert: bool = True,
        cache_dir: Optional[str] = None,
        metadata_store=None,
    ):
        """Initialize the relationship discoverer.

        Args:
            llm_manager: Optional LLM manager for semantic analysis
            use_sbert: Whether to use SBERT embeddings for similarity
            cache_dir: Directory for caching embeddings
            metadata_store: PostgreSQL metadata store for data analysis
        """
        self.llm_manager = llm_manager
        self.metadata_store = metadata_store
        self.use_sbert = use_sbert
        self.cache_dir = cache_dir

        # Initialize SBERT model if requested
        self.sbert_model = None
        if self.use_sbert:
            try:
                self.sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("SBERT model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load SBERT model: {e}")
                self.use_sbert = False

        # Relationship type patterns
        self.relationship_patterns = self._initialize_relationship_patterns()

    def _initialize_relationship_patterns(self) -> dict[str, list[str]]:
        """Initialize patterns for common relationship types."""
        return {
            "foreign_key": ["id", "key", "ref", "reference", "fk", "pk"],
            "temporal": ["date", "time", "created", "updated", "start", "end"],
            "hierarchical": ["parent", "child", "category", "type", "level"],
            "ownership": ["owner", "belongs_to", "has", "contains", "includes"],
            "location": ["address", "city", "state", "country", "location"],
            "measurement": ["amount", "quantity", "size", "weight", "dimension"],
        }

    def discover_relationships(
        self,
        file_path: str,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover relationships between entities.

        Args:
            file_path: Path to the CSV file
            entities: List of extracted entities
            columns: List of column profiles
            config: Discovery configuration

        Returns:
            List of discovered relationships
        """
        logger.info(f"Discovering relationships in {file_path}")

        # Ensure all entities have valid IDs
        for i, entity in enumerate(entities):
            if entity.id is None or entity.id == "":
                # Create a stable ID based on entity name and index
                # Generate deterministic ID based on entity content
                source_cols = [attr.source_column for attr in entity.attributes if attr.source_column]
                content = f"{entity.name}_{entity.entity_type}_{','.join(sorted(source_cols))}"
                entity.id = f"entity_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"

        relationships = []

        # Discover foreign key relationships
        fk_rels = self._discover_foreign_key_relationships(
            file_path, entities, columns, config
        )
        relationships.extend(fk_rels)

        # Discover co-occurrence relationships
        co_occurrence_rels = self._discover_co_occurrence_relationships(
            file_path, entities, columns, config
        )
        relationships.extend(co_occurrence_rels)

        # Discover semantic relationships using SBERT
        semantic_rels = self._discover_semantic_relationships_sbert(
            entities, columns, config
        )
        relationships.extend(semantic_rels)

        # Discover LLM-inferred relationships
        llm_rels = self._discover_llm_relationships(
            file_path, entities, columns, config
        )
        relationships.extend(llm_rels)

        # Discover hierarchical relationships
        hierarchical_rels = self._discover_hierarchical_relationships(
            entities, columns, config
        )
        relationships.extend(hierarchical_rels)

        # Discover temporal relationships
        temporal_rels = self._discover_temporal_relationships(
            file_path, entities, columns, config
        )
        relationships.extend(temporal_rels)

        # Detect relationship cardinality
        relationships = self._detect_relationship_cardinality(
            file_path, relationships, columns, config
        )

        # Remove duplicate relationships
        relationships = self._deduplicate_relationships(relationships)

        # Detect and remove graph cycles
        relationships = self._detect_graph_cycles(relationships)

        logger.info(f"Discovered {len(relationships)} relationships")
        return relationships

    def _discover_foreign_key_relationships(
        self,
        file_path: str,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover foreign key relationships through value overlap analysis."""
        relationships = []

        # Get entity column mapping
        entity_columns = self._get_entity_column_mapping(entities)

        # Find potential foreign key columns
        potential_fk_columns = []
        for col in columns:
            col_lower = col.name.lower()
            if any(
                pattern in col_lower
                for pattern in self.relationship_patterns["foreign_key"]
            ):
                potential_fk_columns.append(col)

        # Analyze value overlap between columns
        for i, col1 in enumerate(columns):
            for col2 in columns[i + 1 :]:
                if col1.name in entity_columns and col2.name in entity_columns:
                    fk_rels = self._analyze_foreign_key_candidate(
                        file_path, col1, col2, entity_columns, config
                    )
                    relationships.extend(fk_rels)

        return relationships

    def _analyze_foreign_key_candidate(
        self,
        file_path: str,
        col1: ColumnProfile,
        col2: ColumnProfile,
        entity_columns: dict[str, list[Entity]],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Analyze if two columns have a foreign key relationship."""
        relationships = []

        try:
            # Get the actual column names from the CSV
            with open(file_path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    headers = [
                        col.strip().strip('"').strip("'")
                        for col in first_line.split(",")
                    ]
                    logger.debug(f"Detected headers: {headers}")

                    # Load CSV data for analysis using pandas
                    df = pd.read_csv(file_path)
                    
                    # Check if the provided column names are valid
                    if col1.name not in df.columns or col2.name not in df.columns:
                        logger.warning(
                            f"Column names not found in CSV: {col1.name}, {col2.name}"
                        )
                        return []

                    # Remove null values and get statistics
                    df_clean = df[[col1.name, col2.name]].dropna()
                    
                    if len(df_clean) == 0:
                        return []
                    
                    unique_col1 = df_clean[col1.name].nunique()
                    unique_col2 = df_clean[col2.name].nunique()
                    total_rows = len(df_clean)

            # Check for foreign key patterns
            if unique_col1 > 0 and unique_col2 > 0:
                # Calculate overlap percentage using pandas
                unique_vals_col1 = set(df_clean[col1.name].unique())
                unique_vals_col2 = set(df_clean[col2.name].unique())
                overlap_count = len(unique_vals_col1.intersection(unique_vals_col2))
                overlap_percentage = overlap_count / min(unique_col1, unique_col2)

                # Determine relationship direction and type
                if overlap_percentage >= _safe_config_get(config, "fk_overlap_threshold", 0.8):
                    if unique_col1 <= unique_col2:
                        source_col, target_col = col1, col2
                        relationship_type = "references"
                    else:
                        source_col, target_col = col2, col1
                        relationship_type = "is_referenced_by"

                    # Calculate confidence based on overlap and data characteristics
                    confidence = self._calculate_fk_confidence(
                        overlap_percentage, unique_col1, unique_col2, total_rows
                    )

                    if confidence >= _safe_config_get(config, "relationship_threshold", 0.6):
                        # Find representative entities
                        source_entity = self._find_representative_entity(
                            source_col, entity_columns
                        )
                        target_entity = self._find_representative_entity(
                            target_col, entity_columns
                        )

                        if source_entity and target_entity:
                            # Get sample evidence
                            evidence = self._get_fk_evidence(
                                file_path, source_col, target_col
                            )

                            relationship = Relationship(
                                id=f"fk_{source_entity.id}_{target_entity.id}_{hash(relationship_type)}",
                                source_entity_id=source_entity.id,
                                target_entity_id=target_entity.id,
                                relationship_type=relationship_type,
                                attributes={
                                    "overlap_percentage": overlap_percentage,
                                    "overlap_count": overlap_count,
                                    "source_column": source_col.name,
                                    "target_column": target_col.name,
                                    "unique_source_values": unique_col1,
                                    "unique_target_values": unique_col2,
                                    "evidence": evidence,
                                    "extraction_method": "foreign_key_analysis",
                                },
                                confidence=confidence,
                                source_columns=[source_col.name, target_col.name],
                            )
                            relationships.append(relationship)

        except Exception as e:
            logger.warning(f"Error analyzing foreign key candidate: {e}")

        return relationships

    def _calculate_fk_confidence(
        self,
        overlap_percentage: float,
        unique_col1: int,
        unique_col2: int,
        total_rows: int,
    ) -> float:
        """Calculate confidence score for foreign key relationship."""
        confidence = overlap_percentage * 0.6  # Base confidence from overlap

        # Bonus for high overlap
        if overlap_percentage >= 0.95:
            confidence += 0.2
        elif overlap_percentage >= 0.8:
            confidence += 0.1

        # Bonus for reasonable cardinality ratios
        if unique_col1 > 0 and unique_col2 > 0:
            ratio = min(unique_col1, unique_col2) / max(unique_col1, unique_col2)
            if 0.1 <= ratio <= 1.0:
                confidence += 0.1

        # Bonus for sufficient data
        if total_rows >= 100:
            confidence += 0.1

        return min(confidence, 1.0)

    def _find_representative_entity(
        self, column: ColumnProfile, entity_columns: dict[str, list[Entity]]
    ) -> Optional[Entity]:
        """Find a representative entity for a column."""
        if column.name not in entity_columns:
            return None

        entities = entity_columns[column.name]
        if not entities:
            return None

        # Return entity with highest confidence
        return max(entities, key=lambda e: e.confidence)

    def _get_fk_evidence(
        self, file_path: str, source_col: ColumnProfile, target_col: ColumnProfile
    ) -> list[dict[str, Any]]:
        """Get sample evidence for foreign key relationship."""
        try:
            # Load CSV data using pandas
            df = pd.read_csv(file_path)
            
            # Check if the provided column names are valid
            if source_col.name not in df.columns or target_col.name not in df.columns:
                logger.warning(
                    f"Column names not found in CSV: {source_col.name}, {target_col.name}"
                )
                return []

            # Get sample evidence (up to 5 rows)
            df_clean = df[[source_col.name, target_col.name]].dropna()
            df_sample = df_clean.head(5)
            
            evidence = []
            for _, row in df_sample.iterrows():
                evidence.append(
                    {
                        "source_value": str(row[source_col.name]),
                        "target_value": str(row[target_col.name]),
                    }
                )

            return evidence

        except Exception as e:
            logger.warning(f"Error getting FK evidence: {e}")
            return []

    def _discover_semantic_relationships_sbert(
        self,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover semantic relationships using SBERT embeddings."""
        relationships = []

        if not self.sbert_model:
            return relationships

        try:
            # Get embeddings for all entities
            entity_texts = []
            entity_map = {}

            for entity in entities:
                text = f"{entity.name} {entity.entity_type}"
                entity_texts.append(text)
                entity_map[text] = entity

            if not entity_texts:
                return relationships

            # Calculate embeddings
            embeddings = self.sbert_model.encode(entity_texts)

            # Find similar entities using cosine similarity
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = cosine_similarity(
                        embeddings[i : i + 1], embeddings[j : j + 1]
                    )[0][0]

                    if similarity >= _safe_config_get(config, "semantic_similarity_threshold", 0.7):
                        entity1 = entity_map[entity_texts[i]]
                        entity2 = entity_map[entity_texts[j]]

                        # Determine relationship type based on similarity
                        relationship_type = (
                            self._infer_relationship_type_from_similarity(
                                entity1, entity2, similarity
                            )
                        )

                        relationship = Relationship(
                            id=f"sbert_{entity1.id}_{entity2.id}_{hash(relationship_type)}",
                            source_entity_id=entity1.id,
                            target_entity_id=entity2.id,
                            relationship_type=relationship_type,
                            attributes={
                                "semantic_similarity": float(similarity),
                                "source_entity_type": entity1.entity_type,
                                "target_entity_type": entity2.entity_type,
                                "extraction_method": "sbert_similarity",
                            },
                            confidence=float(similarity),
                            source_columns=(
                                [entity1.attributes[0].source_column, entity2.attributes[0].source_column]
                                if entity1.attributes and entity2.attributes and 
                                   entity1.attributes[0].source_column and entity2.attributes[0].source_column
                                else []
                            ),
                        )
                        relationships.append(relationship)

        except Exception as e:
            logger.warning(f"SBERT similarity analysis failed: {e}")

        return relationships

    def _infer_relationship_type_from_similarity(
        self, entity1: Entity, entity2: Entity, similarity: float
    ) -> str:
        """Infer relationship type from entity similarity."""
        if similarity >= 0.9:
            return "is_synonym_of"
        elif similarity >= 0.8:
            return "is_similar_to"
        elif similarity >= 0.7:
            return "related_to"
        else:
            return "weakly_related_to"

    def _discover_llm_relationships(
        self,
        file_path: str,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover relationships using LLM inference."""
        relationships = []

        if not self.llm_manager:
            return relationships

        try:
            # Group entities by source column
            entities_by_column = defaultdict(list)
            for entity in entities:
                if entity.attributes and entity.attributes[0].source_column:
                    entities_by_column[entity.attributes[0].source_column].append(entity)

            # Analyze column relationships using LLM
            for col1_name, col1_entities in entities_by_column.items():
                for col2_name, col2_entities in entities_by_column.items():
                    if col1_name != col2_name:
                        llm_rels = self._analyze_column_relationship_with_llm(
                            file_path,
                            col1_name,
                            col2_name,
                            col1_entities,
                            col2_entities,
                            config,
                        )
                        relationships.extend(llm_rels)

        except Exception as e:
            logger.warning(f"LLM relationship discovery failed: {e}")

        return relationships

    def _analyze_column_relationship_with_llm(
        self,
        file_path: str,
        col1_name: str,
        col2_name: str,
        col1_entities: list[Entity],
        col2_entities: list[Entity],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Analyze relationship between two columns using LLM."""
        relationships = []

        try:
            # Get sample data for LLM analysis
            sample_data = self._get_sample_data_for_llm(file_path, col1_name, col2_name)

            if not sample_data:
                return relationships

            # Use LLM to infer relationship
            if not self.llm_manager:
                logger.debug("LLM manager not available, skipping LLM analysis")
                return relationships

            try:
                relationship_info = self.llm_manager.infer_column_relationship(
                    col1_name, col2_name, sample_data
                )
                logger.debug(
                    f"LLM response type: {type(relationship_info)}, content: {relationship_info}"
                )
            except Exception as llm_error:
                logger.warning(f"LLM inference failed: {llm_error}")
                return relationships

            if relationship_info and isinstance(relationship_info, dict):
                confidence = relationship_info.get("confidence", 0)
                relationship_type = relationship_info.get(
                    "relationship_type", "unknown"
                )
                reasoning = relationship_info.get("reasoning", "No reasoning provided")

                logger.debug(
                    f"Processing LLM result: confidence={confidence}, type={relationship_type}"
                )

                if confidence >= _safe_config_get(config, "relationship_threshold", 0.6):
                    # Create relationships for entity pairs
                    for entity1 in col1_entities[
                        :5
                    ]:  # Limit to avoid too many relationships
                        for entity2 in col2_entities[:5]:
                            try:
                                relationship = Relationship(
                                    id=f"llm_{entity1.id}_{entity2.id}_{hash(relationship_type)}",
                                    source_entity_id=entity1.id,
                                    target_entity_id=entity2.id,
                                    relationship_type=relationship_type,
                                    attributes={
                                        "llm_confidence": confidence,
                                        "llm_reasoning": reasoning,
                                        "source_column": col1_name,
                                        "target_column": col2_name,
                                        "evidence": sample_data,
                                        "extraction_method": "llm_inference",
                                    },
                                    confidence=confidence,
                                    source_columns=[col1_name, col2_name],
                                )
                                relationships.append(relationship)
                            except Exception as rel_error:
                                logger.warning(
                                    f"Failed to create relationship: {rel_error}"
                                )
                                continue

        except Exception as e:
            logger.warning(f"LLM column analysis failed: {e}")

        return relationships

    def _get_sample_data_for_llm(
        self, file_path: str, col1_name: str, col2_name: str
    ) -> list[dict[str, Any]]:
        """Get sample data for LLM relationship analysis."""
        try:
            # Load CSV data using pandas
            df = pd.read_csv(file_path)
            
            # Check if the provided column names are valid
            if col1_name not in df.columns or col2_name not in df.columns:
                logger.warning(
                    f"Column names not found in CSV: {col1_name}, {col2_name}"
                )
                logger.info(f"Available columns: {list(df.columns)}")
                return []

            # Get sample data (up to 10 rows)
            df_clean = df[[col1_name, col2_name]].dropna()
            df_sample = df_clean.head(10)
            
            sample_data = []
            for _, row in df_sample.iterrows():
                sample_data.append(
                    {
                        "column1_value": str(row[col1_name]),
                        "column2_value": str(row[col2_name]),
                    }
                )

            return sample_data

        except Exception as e:
            logger.warning(f"Error getting sample data: {e}")
            return []

    def _discover_hierarchical_relationships(
        self,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover hierarchical relationships between entities."""
        relationships = []

        # Look for parent-child relationships in categorical data
        for column in columns:
            if column.data_type == DataType.CATEGORICAL:
                col_entities = [
                    e
                    for e in entities
                    if e.attributes and e.attributes[0].source_column == column.name
                ]

                if len(col_entities) > 1:
                    # Try to find hierarchical patterns
                    hierarchical_rels = self._find_hierarchical_patterns(
                        col_entities, column
                    )
                    relationships.extend(hierarchical_rels)

        return relationships

    def _find_hierarchical_patterns(
        self, entities: list[Entity], column: ColumnProfile
    ) -> list[Relationship]:
        """Find hierarchical patterns in categorical entities."""
        relationships = []

        # Simple approach: look for entities that contain other entities
        for entity1 in entities:
            for entity2 in entities:
                if entity1.id != entity2.id:
                    # Check if one entity name contains the other
                    if (
                        entity1.name.lower() in entity2.name.lower()
                        or entity2.name.lower() in entity1.name.lower()
                    ):

                        # Determine parent-child relationship
                        if len(entity1.name) < len(entity2.name):
                            parent, child = entity1, entity2
                        else:
                            parent, child = entity2, entity1

                        relationship = Relationship(
                            id=f"hier_{parent.id}_{child.id}",
                            source_entity_id=parent.id,
                            target_entity_id=child.id,
                            relationship_type="is_parent_of",
                            attributes={
                                "hierarchy_level": "parent_child",
                                "source_column": column.name,
                            },
                            confidence=0.8,
                            source_columns=[column.name],
                        )
                        relationships.append(relationship)

        return relationships

    def _discover_temporal_relationships(
        self,
        file_path: str,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover temporal relationships between entities."""
        relationships = []

        # Find temporal columns
        temporal_columns = [
            col for col in columns if col.data_type == DataType.DATETIME
        ]

        if not temporal_columns:
            return relationships

        # Find entities that might have temporal relationships
        temporal_entities = [
            e
            for e in entities
            if e.entity_type == "temporal"
            or any(
                col.name in [attr.source_column for attr in e.attributes if attr.source_column]
                for col in temporal_columns
            )
        ]

        # Create temporal sequence relationships
        for i, entity1 in enumerate(temporal_entities):
            for entity2 in temporal_entities[i + 1 :]:
                relationship = Relationship(
                    id=f"temp_{entity1.id}_{entity2.id}",
                    source_entity_id=entity1.id,
                    target_entity_id=entity2.id,
                    relationship_type="precedes",
                    attributes={
                        "temporal_relationship": "sequence",
                        "source_columns": (
                            [entity1.attributes[0].source_column, entity2.attributes[0].source_column]
                            if entity1.attributes and entity2.attributes and 
                               entity1.attributes[0].source_column and entity2.attributes[0].source_column
                            else []
                        ),
                    },
                    confidence=0.7,
                    source_columns=(
                        [entity1.attributes[0].source_column, entity2.attributes[0].source_column]
                        if entity1.attributes and entity2.attributes and 
                           entity1.attributes[0].source_column and entity2.attributes[0].source_column
                        else []
                    ),
                )
                relationships.append(relationship)

        return relationships

    def _deduplicate_relationships(
        self, relationships: list[Relationship]
    ) -> list[Relationship]:
        """Remove duplicate relationships."""
        if not relationships:
            return []

        # Group by source, target, and type
        relationship_groups = defaultdict(list)

        for rel in relationships:
            key = (rel.source_entity_id, rel.target_entity_id, rel.relationship_type)
            relationship_groups[key].append(rel)

        # Keep the relationship with highest confidence
        unique_relationships = []
        for group in relationship_groups.values():
            best_rel = max(group, key=lambda r: r.confidence)
            unique_relationships.append(best_rel)

        return unique_relationships

    def _detect_relationship_cardinality(
        self,
        file_path: str,
        relationships: list[Relationship],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Detect relationship cardinality (1:1, 1:n, n:m)."""
        for relationship in relationships:
            if (
                "source_column" in relationship.attributes
                and "target_column" in relationship.attributes
            ):
                source_col = relationship.attributes["source_column"]
                target_col = relationship.attributes["target_column"]

                cardinality = self._calculate_cardinality(
                    file_path, source_col, target_col
                )
                relationship.attributes["cardinality"] = cardinality

                # Adjust confidence based on cardinality consistency
                if (
                    cardinality == "1:1"
                    and relationship.attributes.get("overlap_percentage", 0) >= 0.95
                ):
                    relationship.confidence = min(relationship.confidence + 0.1, 1.0)
                elif (
                    cardinality == "n:m"
                    and relationship.attributes.get("overlap_percentage", 0) <= 0.3
                ):
                    relationship.confidence = min(relationship.confidence + 0.05, 1.0)

        return relationships

    def _calculate_cardinality(
        self, file_path: str, source_col: str, target_col: str
    ) -> str:
        """Calculate cardinality between two columns."""
        try:
            # Load CSV data using pandas
            df = pd.read_csv(file_path)
            
            # Check if the provided column names are valid
            if source_col not in df.columns or target_col not in df.columns:
                logger.warning(
                    f"Column names not found in CSV: {source_col}, {target_col}"
                )
                return "unknown"

            # Calculate cardinality using pandas
            df_clean = df[[source_col, target_col]].dropna()
            
            if len(df_clean) == 0:
                return "unknown"
            
            unique_source = df_clean[source_col].nunique()
            unique_target = df_clean[target_col].nunique()
            total_rows = len(df_clean)

            if unique_source == 0 or unique_target == 0:
                return "unknown"

            # Calculate cardinality ratios
            source_to_target = unique_source / unique_target
            target_to_source = unique_target / unique_source

            if source_to_target <= 1.1 and target_to_source <= 1.1:
                return "1:1"
            elif source_to_target <= 0.1:
                return "1:n"
            elif target_to_source <= 0.1:
                return "n:1"
            else:
                return "n:m"

        except Exception as e:
            logger.warning(f"Error calculating cardinality: {e}")
            return "unknown"

    def _detect_graph_cycles(
        self, relationships: list[Relationship]
    ) -> list[Relationship]:
        """Detect and remove graph cycles to avoid redundant relationships."""
        if not relationships:
            return relationships

        try:
            # Create directed graph
            G = nx.DiGraph()

            # Add edges
            for rel in relationships:
                G.add_edge(rel.source_entity_id, rel.target_entity_id, relationship=rel)

            # Find cycles
            cycles = list(nx.simple_cycles(G))

            if cycles:
                logger.info(f"Detected {len(cycles)} cycles in relationship graph")

                # Remove relationships that create cycles
                relationships_to_remove = set()
                for cycle in cycles:
                    if len(cycle) > 1:
                        # Find the relationship with lowest confidence in the cycle
                        min_confidence = float("inf")
                        rel_to_remove = None

                        for i in range(len(cycle)):
                            source = cycle[i]
                            target = cycle[(i + 1) % len(cycle)]

                            # Find the relationship
                            for rel in relationships:
                                if (
                                    rel.source_entity_id == source
                                    and rel.target_entity_id == target
                                ):
                                    if rel.confidence < min_confidence:
                                        min_confidence = rel.confidence
                                        rel_to_remove = rel
                                    break

                        if rel_to_remove:
                            relationships_to_remove.add(rel_to_remove.id)

                # Filter out relationships that create cycles
                filtered_relationships = [
                    rel
                    for rel in relationships
                    if rel.id not in relationships_to_remove
                ]

                logger.info(
                    f"Removed {len(relationships) - len(filtered_relationships)} cycle-creating relationships"
                )
                return filtered_relationships

        except Exception as e:
            logger.warning(f"Graph cycle detection failed: {e}")

        return relationships

    def _discover_co_occurrence_relationships(
        self,
        file_path: str,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover relationships based on co-occurrence in rows."""
        relationships = []

        # Get entity column mapping
        entity_columns = self._get_entity_column_mapping(entities)

        # Find columns that might have relationships
        potential_relation_columns = [
            col
            for col in columns
            if col.data_type in [DataType.STRING, DataType.CATEGORICAL]
        ]

        for i, col1 in enumerate(potential_relation_columns):
            for col2 in potential_relation_columns[i + 1 :]:
                # Check if these columns have entities
                if col1.name in entity_columns and col2.name in entity_columns:
                    rels = self._analyze_column_relationship(
                        file_path, col1, col2, entity_columns, config
                    )
                    relationships.extend(rels)

        return relationships

    def _get_entity_column_mapping(
        self, entities: list[Entity]
    ) -> dict[str, list[Entity]]:
        """Create mapping from column names to entities."""
        mapping = defaultdict(list)
        for entity in entities:
            if entity.attributes and entity.attributes[0].source_column:
                mapping[entity.attributes[0].source_column].append(entity)
        return dict(mapping)

    def _analyze_column_relationship(
        self,
        file_path: str,
        col1: ColumnProfile,
        col2: ColumnProfile,
        entity_columns: dict[str, list[Entity]],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Analyze relationship between two columns."""
        relationships = []

        try:
            # Load CSV data using pandas
            df = pd.read_csv(file_path)
            
            # Check if the provided column names are valid
            if col1.name not in df.columns or col2.name not in df.columns:
                logger.warning(
                    f"Column names not found in CSV: {col1.name}, {col2.name}"
                )
                return []

            # Get co-occurrence data using pandas
            df_clean = df[[col1.name, col2.name]].dropna()
            
            if len(df_clean) == 0:
                return []
            
            # Group by both columns and count occurrences
            co_occurrence = df_clean.groupby([col1.name, col2.name]).size().reset_index(name='co_count')
            co_occurrence = co_occurrence[co_occurrence['co_count'] > 1].sort_values('co_count', ascending=False).head(100)
            
            if len(co_occurrence) == 0:
                return []

            # Calculate relationship strength
            total_rows = co_occurrence["co_count"].sum()

            for _, row in co_occurrence.iterrows():
                val1 = row[col1.name]
                val2 = row[col2.name]
                co_count = row['co_count']

                # Find corresponding entities
                entity1 = self._find_entity_by_value(val1, entity_columns[col1.name])
                entity2 = self._find_entity_by_value(val2, entity_columns[col2.name])

                if entity1 and entity2:
                    # Calculate confidence based on co-occurrence frequency
                    confidence = min(co_count / total_rows * 10, 0.95)

                    if confidence >= _safe_config_get(config, "relationship_threshold", 0.6):
                        relationship = Relationship(
                            id=f"co_{entity1.id}_{entity2.id}_{hash(f'{val1}_{val2}')}",
                            source_entity_id=entity1.id,
                            target_entity_id=entity2.id,
                            relationship_type="co_occurs_with",
                            attributes={
                                "co_occurrence_count": int(co_count),
                                "source_column": col1.name,
                                "target_column": col2.name,
                                "source_value": str(val1),
                                "target_value": str(val2),
                                "extraction_method": "co_occurrence_analysis",
                            },
                            confidence=confidence,
                            source_columns=[col1.name, col2.name],
                        )
                        relationships.append(relationship)

        except Exception as e:
            logger.warning(f"Error analyzing column relationship: {e}")

        return relationships

    def _find_entity_by_value(
        self, value: Any, entities: list[Entity]
    ) -> Optional[Entity]:
        """Find entity by its source value."""
        for entity in entities:
            if entity.source_value == str(value):
                return entity
        return None

    def _discover_semantic_relationships(
        self,
        entities: list[Entity],
        columns: list[ColumnProfile],
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Discover semantic relationships using LLM and similarity analysis."""
        relationships = []

        if not self.llm_manager:
            return relationships

        # Group entities by type
        entities_by_type = defaultdict(list)
        for entity in entities:
            entities_by_type[entity.entity_type].append(entity)

        # Find semantic relationships between different entity types
        for entity_type1, entities1 in entities_by_type.items():
            for entity_type2, entities2 in entities_by_type.items():
                if entity_type1 != entity_type2:
                    rels = self._analyze_semantic_relationship(
                        entities1, entities2, entity_type1, entity_type2, config
                    )
                    relationships.extend(rels)

        return relationships

    def _analyze_semantic_relationship(
        self,
        entities1: list[Entity],
        entities2: list[Entity],
        type1: str,
        type2: str,
        config: dict[str, Any],
    ) -> list[Relationship]:
        """Analyze semantic relationship between two entity types."""
        relationships = []

        # Use LLM to determine relationship type
        try:
            if self.llm_manager:
                relationship_type = self.llm_manager.suggest_relationship_type(
                    type1, type2
                )
                if not relationship_type:
                    relationship_type = "related_to"
            else:
                relationship_type = "related_to"
        except Exception as e:
            logger.warning(f"LLM relationship suggestion failed: {e}")
            relationship_type = "related_to"

        # Create relationships for high-confidence entity pairs
        for entity1 in entities1[:10]:  # Limit to avoid too many relationships
            for entity2 in entities2[:10]:
                # Calculate semantic similarity
                similarity = self._calculate_semantic_similarity(entity1, entity2)

                if similarity >= _safe_config_get(config, "relationship_threshold", 0.6):
                    relationship = Relationship(
                        id=f"sem_{entity1.id}_{entity2.id}_{hash(relationship_type)}",
                        source_entity_id=entity1.id,
                        target_entity_id=entity2.id,
                        relationship_type=relationship_type,
                        attributes={
                            "semantic_similarity": similarity,
                            "source_entity_type": type1,
                            "target_entity_type": type2,
                            "extraction_method": "semantic_analysis",
                        },
                        confidence=similarity,
                        source_columns=(
                            [entity1.source_columns[0], entity2.source_columns[0]]
                            if entity1.source_columns and entity2.source_columns
                            else []
                        ),
                    )
                    relationships.append(relationship)

        return relationships

    def _calculate_semantic_similarity(self, entity1: Entity, entity2: Entity) -> float:
        """Calculate semantic similarity between two entities."""
        # Simple text similarity for now
        text1 = f"{entity1.name} {entity1.entity_type}"
        text2 = f"{entity2.name} {entity2.entity_type}"

        # Use TF-IDF and cosine similarity
        try:
            vectorizer = TfidfVectorizer(lowercase=True, stop_words="english")
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception:
            return 0.0

    def get_relationship_statistics(
        self, relationships: list[Relationship]
    ) -> dict[str, Any]:
        """Get statistics about discovered relationships."""
        if not relationships:
            return {}

        # Count by relationship type
        type_counts = defaultdict(int)
        for rel in relationships:
            type_counts[rel.relationship_type] += 1

        # Calculate average confidence
        avg_confidence = sum(rel.confidence for rel in relationships) / len(
            relationships
        )

        # Count by source columns
        column_counts = defaultdict(int)
        for rel in relationships:
            for col in rel.source_columns:
                column_counts[col] += 1

        # Count by extraction method
        method_counts = defaultdict(int)
        for rel in relationships:
            method = rel.attributes.get("extraction_method", "unknown")
            method_counts[method] += 1

        # Count by cardinality
        cardinality_counts = defaultdict(int)
        for rel in relationships:
            cardinality = rel.attributes.get("cardinality", "unknown")
            cardinality_counts[cardinality] += 1

        return {
            "total_relationships": len(relationships),
            "relationship_types": dict(type_counts),
            "average_confidence": avg_confidence,
            "columns_with_relationships": dict(column_counts),
            "extraction_methods": dict(method_counts),
            "cardinality_distribution": dict(cardinality_counts),
            "most_common_relationship_type": (
                max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else None
            ),
        }

    def get_relationship_evidence(
        self, relationship: Relationship, file_path: str
    ) -> dict[str, Any]:
        """Get detailed evidence for a specific relationship."""
        evidence = {
            "relationship_id": relationship.id,
            "source_entity_id": relationship.source_entity_id,
            "target_entity_id": relationship.target_entity_id,
            "relationship_type": relationship.relationship_type,
            "confidence": relationship.confidence,
            "attributes": relationship.attributes.copy(),
            "source_columns": relationship.source_columns.copy(),
        }

        # Add specific evidence based on extraction method
        extraction_method = relationship.attributes.get("extraction_method", "")

        if extraction_method == "foreign_key_analysis":
            evidence["fk_evidence"] = {
                "overlap_percentage": relationship.attributes.get("overlap_percentage"),
                "overlap_count": relationship.attributes.get("overlap_count"),
                "unique_source_values": relationship.attributes.get(
                    "unique_source_values"
                ),
                "unique_target_values": relationship.attributes.get(
                    "unique_target_values"
                ),
            }

        elif extraction_method == "sbert_similarity":
            evidence["semantic_evidence"] = {
                "semantic_similarity": relationship.attributes.get(
                    "semantic_similarity"
                ),
                "source_entity_type": relationship.attributes.get("source_entity_type"),
                "target_entity_type": relationship.attributes.get("target_entity_type"),
            }

        elif extraction_method == "llm_inference":
            evidence["llm_evidence"] = {
                "llm_confidence": relationship.attributes.get("llm_confidence"),
                "llm_reasoning": relationship.attributes.get("llm_reasoning"),
                "sample_data": relationship.attributes.get("evidence", []),
            }

        elif extraction_method == "co_occurrence_analysis":
            evidence["co_occurrence_evidence"] = {
                "co_occurrence_count": relationship.attributes.get(
                    "co_occurrence_count"
                ),
                "source_value": relationship.attributes.get("source_value"),
                "target_value": relationship.attributes.get("target_value"),
            }

        # Add cardinality information
        if "cardinality" in relationship.attributes:
            evidence["cardinality"] = relationship.attributes["cardinality"]

        return evidence

    def export_relationships_to_graph(
        self, relationships: list[Relationship], entities: list[Entity]
    ) -> dict[str, Any]:
        """Export relationships to a graph format for visualization."""
        graph_data = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "total_nodes": len(entities),
                "total_edges": len(relationships),
                "node_types": {},
                "edge_types": {},
            },
        }

        # Add nodes (entities)
        for entity in entities:
            node = {
                "id": entity.id,
                "label": entity.name,
                "type": entity.entity_type,
                "confidence": entity.confidence,
                "source_column": (
                    entity.attributes[0].source_column if entity.attributes and entity.attributes[0].source_column else None
                ),
                "attributes": entity.attributes,
            }
            graph_data["nodes"].append(node)

            # Count node types
            entity_type = entity.entity_type
            graph_data["metadata"]["node_types"][entity_type] = (
                graph_data["metadata"]["node_types"].get(entity_type, 0) + 1
            )

        # Add edges (relationships)
        for relationship in relationships:
            edge = {
                "id": relationship.id,
                "source": relationship.source_entity_id,
                "target": relationship.target_entity_id,
                "type": relationship.relationship_type,
                "confidence": relationship.confidence,
                "cardinality": relationship.attributes.get("cardinality", "unknown"),
                "extraction_method": relationship.attributes.get(
                    "extraction_method", "unknown"
                ),
                "attributes": relationship.attributes,
            }
            graph_data["edges"].append(edge)

            # Count edge types
            edge_type = relationship.relationship_type
            graph_data["metadata"]["edge_types"][edge_type] = (
                graph_data["metadata"]["edge_types"].get(edge_type, 0) + 1
            )

        return graph_data

    def validate_relationships(
        self, relationships: list[Relationship], entities: list[Entity]
    ) -> dict[str, Any]:
        """Validate discovered relationships for consistency and quality."""
        validation_results = {
            "total_relationships": len(relationships),
            "valid_relationships": 0,
            "invalid_relationships": 0,
            "validation_errors": [],
            "quality_metrics": {},
        }

        # Track entity IDs for validation
        entity_ids = {entity.id for entity in entities}

        for relationship in relationships:
            is_valid = True
            errors = []

            # Check if source and target entities exist
            if relationship.source_entity_id not in entity_ids:
                is_valid = False
                errors.append(
                    f"Source entity {relationship.source_entity_id} not found"
                )

            if relationship.target_entity_id not in entity_ids:
                is_valid = False
                errors.append(
                    f"Target entity {relationship.target_entity_id} not found"
                )

            # Check for self-relationships
            if relationship.source_entity_id == relationship.target_entity_id:
                is_valid = False
                errors.append("Self-relationship detected")

            # Check confidence range
            if not (0.0 <= relationship.confidence <= 1.0):
                is_valid = False
                errors.append(f"Invalid confidence score: {relationship.confidence}")

            # Check required attributes
            if not relationship.attributes:
                is_valid = False
                errors.append("Missing attributes")

            if not relationship.source_columns:
                is_valid = False
                errors.append("Missing source columns")

            # Update validation results
            if is_valid:
                validation_results["valid_relationships"] += 1
            else:
                validation_results["invalid_relationships"] += 1
                validation_results["validation_errors"].extend(errors)

        # Calculate quality metrics
        if validation_results["total_relationships"] > 0:
            validation_results["quality_metrics"] = {
                "validity_rate": validation_results["valid_relationships"]
                / validation_results["total_relationships"],
                "average_confidence": sum(r.confidence for r in relationships)
                / len(relationships),
                "confidence_distribution": {
                    "high": len([r for r in relationships if r.confidence >= 0.8]),
                    "medium": len(
                        [r for r in relationships if 0.6 <= r.confidence < 0.8]
                    ),
                    "low": len([r for r in relationships if r.confidence < 0.6]),
                },
            }

        return validation_results
