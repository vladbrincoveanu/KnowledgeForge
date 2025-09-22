"""Ontology extraction endpoints."""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.domain.models.entities import DatasetProfile, Entity, Relationship
from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.storage.metadata_store import (
    PostgreSQLMetadataStore as MetadataStore,
)

# Import actual backend services
from app.services.entity_extraction.entity_extractor import EntityExtractor
from app.services.ontology_mapping.ontology_mapper import OntologyMapper
from app.services.relationship_discovery.relationship_discoverer import (
    RelationshipDiscoverer,
)
from app.services.recommendation.recommendation_service import RecommendationService
from utils.config import get_config
from app.domain.models.recommendations import (
    EdgeRecommendation,
    NodeRecommendation,
    RecommendationSession,
)
from app.endpoint.v1.routes.websocket import (
    broadcast_task_update,
    broadcast_extraction_complete,
)

logger = logging.getLogger(__name__)


class ExtractionRequest(BaseModel):
    """Request model for extraction operations."""

    file_path: str = Field(..., description="Path to the file to extract from")
    extraction_config: Optional[dict[str, Any]] = Field(
        None, description="Optional extraction configuration"
    )


class ExtractionResponse(BaseModel):
    """Response model for extraction operations."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )


class ExtractionTask:
    """Manages extraction task state and progress."""

    def __init__(self, task_id: str, file_path: str):
        self.task_id = task_id
        self.file_path = file_path
        self.status = "pending"
        self.progress = 0.0
        self.entities: list[Entity] = []
        self.relationships: list[Relationship] = []
        self.errors: list[str] = []
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.dataset_profile: Optional[DatasetProfile] = None
        self.extraction_config: Optional[dict[str, Any]] = None
        self.recommendation_session: Optional[RecommendationSession] = None


# In-memory task storage (replace with Redis/database in production)
extraction_tasks: dict[str, ExtractionTask] = {}

router = APIRouter(tags=["extraction"])


# Dependency injection
_recommendation_service: Optional[RecommendationService] = None

def get_entity_extractor():
    """Get entity extractor instance."""

    
    config = get_config()
    
    # Create LLM manager for enhanced entity extraction
    try:
        from app.infrastructure.llm.llm_manager import LLMManager
        llm_manager = LLMManager(
            lmstudio_url=config.lmstudio.base_url if hasattr(config, 'lmstudio') else "http://localhost:1234",
            default_model=config.lmstudio.model_name if hasattr(config, 'lmstudio') else "deepseek/deepseek-r1-0528-qwen3-8b"
        )
    except Exception as e:
        logger.warning(f"Failed to create LLM manager: {e}")
        llm_manager = None
    
    return EntityExtractor(
        cache_dir=(
            config.extraction.cache_dir
            if hasattr(config.extraction, "cache_dir")
            else None
        ),
        llm_manager=llm_manager,
    )


def get_ontology_mapper():
    """Get ontology mapper instance."""
    config = get_config()
    return OntologyMapper(
        cache_dir=(
            config.extraction.cache_dir
            if hasattr(config.extraction, "cache_dir")
            else None
        )
    )


def get_neo4j_manager():
    """Get Neo4j manager instance."""
    config = get_config()
    manager = Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database,
        encrypted=config.neo4j.encrypted,
    )
    # Connect immediately to ensure the connection is established
    manager.connect()
    return manager


def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config=config)


def _safe_uuid(value: Any) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception:
        return uuid.uuid4()


def _to_node_recommendation(
    payload: Any, session_id: uuid.UUID
) -> NodeRecommendation:
    if isinstance(payload, NodeRecommendation):
        data = payload.model_dump(mode="python")
    elif hasattr(payload, "dict"):
        data = payload.dict()
    else:
        data = dict(payload or {})

    metadata = data.get("llm_metadata") or data.get("metadata") or {}
    source_columns = (
        data.get("source_columns")
        or data.get("sourceColumns")
        or metadata.get("source_columns")
        or []
    )

    identifier = data.get("id") or uuid.uuid4()

    return NodeRecommendation(
        id=_safe_uuid(identifier),
        session_id=session_id,
        recommended_name=data.get("recommended_name")
        or data.get("name")
        or "Suggested Node",
        entity_type=data.get("entity_type")
        or data.get("entityType")
        or "unknown",
        confidence_score=float(
            data.get("confidence_score")
            or data.get("confidence")
            or metadata.get("confidence_score")
            or 0.0
        ),
        reasoning=data.get("reasoning")
        or metadata.get("reasoning")
        or "Recommendation provided by LLM",
        source_columns=list(source_columns),
        llm_metadata=metadata,
        user_feedback=data.get("user_feedback"),
        created_at=data.get("created_at") or datetime.utcnow(),
    )


def _to_edge_recommendation(
    payload: Any, session_id: uuid.UUID
) -> EdgeRecommendation:
    if isinstance(payload, EdgeRecommendation):
        data = payload.model_dump(mode="python")
    elif hasattr(payload, "dict"):
        data = payload.dict()
    else:
        data = dict(payload or {})

    metadata = data.get("connection_evidence") or data.get("metadata") or {}

    identifier = data.get("id") or uuid.uuid4()

    return EdgeRecommendation(
        id=_safe_uuid(identifier),
        session_id=session_id,
        source_node_id=_safe_uuid(
            data.get("source_node_id")
            or data.get("sourceNodeId")
            or metadata.get("source_node_id")
        ),
        target_node_id=_safe_uuid(
            data.get("target_node_id")
            or data.get("targetNodeId")
            or metadata.get("target_node_id")
        ),
        relationship_type=data.get("relationship_type")
        or data.get("relationshipType")
        or "RELATED_TO",
        confidence_score=float(
            data.get("confidence_score")
            or data.get("confidence")
            or metadata.get("confidence_score")
            or 0.0
        ),
        reasoning=data.get("reasoning")
        or metadata.get("reasoning")
        or "Relationship recommended by LLM",
        connection_evidence=metadata,
        user_feedback=data.get("user_feedback"),
        created_at=data.get("created_at") or datetime.utcnow(),
    )


def _build_fallback_recommendations(
    task_id: str,
    entities: list[Entity],
    dataset_profile: Optional[DatasetProfile],
) -> Optional[RecommendationSession]:
    """Create a lightweight recommendation session when no LLM is available."""

    if not entities:
        # No entities to suggest names for;
        # attempt to derive from dataset columns if available.
        if dataset_profile and dataset_profile.columns:
            synthetic_entities: list[Entity] = []
            for column in dataset_profile.columns:
                synthetic_entities.append(
                    Entity(
                        id=str(uuid.uuid4()),
                        name=column.name,
                        entity_type=column.data_type.value,
                        confidence=0.5,
                        source_columns=[column.name],
                        attributes={
                            "profiled_unique_count": column.unique_count,
                            "profiled_null_count": column.null_count,
                        },
                    )
                )
            entities.extend(synthetic_entities)
        else:
            return None

    session = RecommendationSession(task_id=task_id, metadata={"source": "fallback"})

    node_recommendations: list[NodeRecommendation] = []

    entity_to_node: dict[str, NodeRecommendation] = {}

    for entity in entities:
        display_name = entity.name or "Suggested Node"
        node = NodeRecommendation(
            id=uuid.uuid4(),
            session_id=session.id,
            recommended_name=display_name,
            entity_type=entity.entity_type or "unknown",
            confidence_score=float(getattr(entity, "confidence", 0.5) or 0.5),
            reasoning="Auto generated from dataset profile",
            source_columns=list(entity.source_columns or []),
            llm_metadata={
                "fallback": True,
                "source_entity_id": entity.id,
            },
        )
        node_recommendations.append(node)
        if entity.id:
            entity_to_node[str(entity.id)] = node

    session.node_recommendations = node_recommendations
    edge_recommendations: list[EdgeRecommendation] = []

    used_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for entity in entities:
        if not entity.source_columns:
            continue

        source_node = entity_to_node.get(str(entity.id))
        if not source_node:
            continue

        for column in entity.source_columns:
            column_lower = column.lower()
            if column_lower.endswith("_id"):
                prefix = column_lower[:-3]
            elif column_lower.startswith("id_"):
                prefix = column_lower[3:]
            else:
                continue

            target_node = None
            target_entity: Optional[Entity] = None
            for other in entities:
                if other is entity:
                    continue
                other_name = (other.name or "").lower()
                if prefix and prefix in other_name:
                    candidate_node = entity_to_node.get(str(other.id))
                    if candidate_node:
                        target_node = candidate_node
                        target_entity = other
                        break

            if not target_node:
                continue

            pair = (source_node.id, target_node.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)

            edge_recommendations.append(
                EdgeRecommendation(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    relationship_type="REFERENCES",
                    confidence_score=0.55,
                    reasoning=f"Column '{column}' suggests a reference from {entity.name or 'source'} to {(target_entity.name if target_entity else 'target')}.",
                    connection_evidence={
                        "fallback": True,
                        "source_column": column,
                        "detected_prefix": prefix,
                    },
                )
            )

    session.edge_recommendations = edge_recommendations
    return session if node_recommendations else None


def _persist_entities_feedback(
    neo4j_manager: Neo4jGraphManager,
    entities: list[Entity],
    task_id: str,
    file_path: Optional[str],
):
    """Upsert approved entities into Neo4j."""

    if not entities:
        return

    file_name = os.path.basename(file_path) if file_path else task_id

    try:
        if not neo4j_manager.is_connected():
            if not neo4j_manager.connect():
                logger.warning("Unable to connect to Neo4j while persisting entity feedback")
                return
    except Exception as connect_error:
        logger.error("Neo4j connection failed during feedback persistence: %s", connect_error)
        return

    for entity in entities:
        try:
            if not getattr(entity, "id", None):
                entity.id = f"entity_{uuid.uuid4().hex[:12]}"

            neo4j_manager.store_entity_with_metadata(
                entity=entity,
                source_file=file_name,
                extraction_timestamp=datetime.now(),
                task_id=task_id,
            )
        except Exception as store_error:
            logger.error("Failed to persist entity feedback for %s: %s", entity.id, store_error)


def _persist_relationships_feedback(
    neo4j_manager: Neo4jGraphManager,
    relationships: list[Relationship],
):
    """Upsert approved relationships into Neo4j."""

    if not relationships:
        return

    try:
        if not neo4j_manager.is_connected():
            if not neo4j_manager.connect():
                logger.warning("Unable to connect to Neo4j while persisting relationship feedback")
                return
    except Exception as connect_error:
        logger.error("Neo4j connection failed during relationship persistence: %s", connect_error)
        return

    for relationship in relationships:
        if not relationship.source_entity_id or not relationship.target_entity_id:
            continue

        try:
            if not getattr(relationship, "id", None):
                content = (
                    f"{relationship.source_entity_id}_{relationship.target_entity_id}_"
                    f"{relationship.relationship_type}"
                )
                relationship.id = f"rel_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"

            neo4j_manager.store_relationship_with_metadata(
                relationship=relationship,
                discovered_at=datetime.now(),
            )
        except Exception as store_error:
            logger.error(
                "Failed to persist relationship feedback for %s: %s",
                getattr(relationship, "id", "NO_ID"),
                store_error,
            )


def get_relationship_discoverer():
    """Get relationship discoverer instance."""
    from app.infrastructure.llm.llm_manager import LLMManager

    config = get_config()
    llm_manager = None
    metadata_store = None
    
    # Initialize LLM manager if configured
    if hasattr(config, 'llm') and config.llm.enabled:
        try:
            llm_manager = LLMManager(
                base_url=config.llm.base_url,
                api_key=config.llm.api_key,
                model=config.llm.model,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize LLM manager: {e}")
    
    # Initialize metadata store for PostgreSQL access
    try:
        metadata_store = MetadataStore(config=config)
    except Exception as e:
        logger.warning(f"Failed to initialize metadata store: {e}")
    
    return RelationshipDiscoverer(
        llm_manager=llm_manager,
        use_sbert=True,  # Enable SBERT for semantic similarity
        cache_dir=None,  # Use default cache directory
        metadata_store=metadata_store,
    )


def get_recommendation_service() -> Optional[RecommendationService]:
    """Get or construct the recommendation service when dependencies are available."""

    global _recommendation_service

    if _recommendation_service is not None:
        return _recommendation_service

    config = get_config()

    try:
        from app.infrastructure.llm.llm_manager import LLMManager

        llm_manager = LLMManager(
            lmstudio_url=getattr(config.lmstudio, "base_url", "http://localhost:1234"),
            default_model=getattr(
                config.lmstudio, "model_name", "deepseek/deepseek-r1-0528-qwen3-8b"
            ),
            use_embeddings=getattr(config.lmstudio, "use_embeddings", True),
        )
    except Exception as exc:
        logger.warning(
            "Recommendation service disabled: failed to initialize LLM manager: %s",
            exc,
        )
        llm_manager = None

    try:
        metadata_store = MetadataStore(config=config)
    except Exception as exc:
        logger.warning(
            "Recommendation service disabled: failed to initialize metadata store: %s",
            exc,
        )
        metadata_store = None

    if not llm_manager or not metadata_store:
        return None

    _recommendation_service = RecommendationService(
        llm_manager=llm_manager,
        metadata_store=metadata_store,
        use_reinforcement_learning=True,
    )
    return _recommendation_service


@router.post("/upload", response_model=dict[str, Any])
async def upload_csv_file(
    file: UploadFile = File(...),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """
    Upload a CSV file for processing.

    This endpoint accepts CSV files and stores them for ontology extraction.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received")

    try:
        # Validate file type
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Create unique filename
        file_id = str(uuid.uuid4())
        file_path = f"uploads/{file_id}_{file.filename}"

        # Ensure uploads directory exists
        Path("uploads").mkdir(exist_ok=True)

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        # Store file metadata
        file_metadata = {
            "file_id": file_id,
            "original_filename": file.filename,
            "file_path": file_path,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "status": "uploaded",
        }

        # Store in metadata store
        metadata_store.register_file(
            file_path=file_path,
            file_name=file.filename,
            file_size=len(content),
            file_type="csv",
        )

        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": file_path,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "message": "File uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/tasks")
async def list_extraction_tasks():
    """List all extraction tasks and their status."""
    try:
        tasks_summary = []
        for task_id, task in extraction_tasks.items():
            tasks_summary.append({
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "entities_count": len(task.entities),
                "relationships_count": len(task.relationships),
                "has_errors": len(task.errors) > 0,
            })
        
        return {
            "tasks": tasks_summary,
            "total_tasks": len(tasks_summary),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Failed to list extraction tasks: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list extraction tasks: {str(e)}"
        )


@router.post("/", response_model=ExtractionResponse)
async def extract_ontology(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
    ontology_mapper: OntologyMapper = Depends(get_ontology_mapper),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    relationship_discoverer: RelationshipDiscoverer = Depends(get_relationship_discoverer),
):
    """
    Process CSV file and extract ontology.

    This endpoint starts an asynchronous ontology extraction process.
    Use the returned task_id to track progress via GET /extract/{task_id}.
    """
    try:
        # Validate that the file exists
        if not Path(request.file_path).exists():
            raise HTTPException(
                status_code=400, detail=f"File not found: {request.file_path}"
            )

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Create extraction task
        task = ExtractionTask(task_id, request.file_path)
        task.extraction_config = request.extraction_config or {}
        extraction_tasks[task_id] = task

        # Add background task for extraction
        background_tasks.add_task(
            run_extraction_pipeline,
            task_id,
            request.file_path,
            request.extraction_config,
            entity_extractor,
            ontology_mapper,
            neo4j_manager,
            metadata_store,
            relationship_discoverer,
        )

        return ExtractionResponse(
            task_id=task_id,
            status="pending",
            message="Extraction task created and queued",
            created_at=datetime.now(),
            estimated_completion=datetime.now() + timedelta(minutes=5),
        )

    except Exception as e:
        logger.error(f"Failed to create extraction task: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create extraction task: {str(e)}"
        )



async def continue_extraction_pipeline(
    task_id: str,
    extraction_config: dict[str, Any],
    ontology_mapper: OntologyMapper,
    neo4j_manager: Neo4jGraphManager,
    metadata_store: MetadataStore,
    relationship_discoverer: RelationshipDiscoverer,
):
    """Continue extraction pipeline after human feedback."""
    try:
        task = extraction_tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found for continuation")
            return

        logger.info(f"Continuing extraction pipeline for task {task_id}")
        
        # Update task status
        task.status = "processing"
        task.progress = 0.7
        
        # Continue with ontology mapping and relationship discovery
        if task.entities:
            # Map entities to ontology
            ontology_result = await ontology_mapper.map_entities_to_ontology(
                task.entities, task.dataset_profile
            )
            if ontology_result:
                task.ontology_mapping = ontology_result
                task.progress = 0.8
                
                # Discover relationships
                columns = task.dataset_profile.columns if hasattr(task.dataset_profile, 'columns') else []
                relationships = relationship_discoverer.discover_relationships(
                    task.file_path or "",
                    task.entities,
                    columns,
                    task.extraction_config or {}
                )
                task.relationships = relationships
                task.progress = 0.9
                
                # Store in Neo4j
                await store_results_in_neo4j(
                    task_id, task.entities, task.relationships, neo4j_manager
                )
                
                # Complete the task
                task.status = "completed"
                task.progress = 1.0
                task.completed_at = datetime.utcnow()
                
                # Update metadata store
                metadata_store.complete_extraction_run(
                    task_id, "completed", {
                        "entities_count": len(task.entities),
                        "relationships_count": len(task.relationships),
                        "ontology_mapping": ontology_result
                    }
                )
                
                logger.info(f"Successfully completed extraction pipeline for task {task_id}")
            else:
                task.status = "failed"
                task.error_message = "Failed to map entities to ontology"
                metadata_store.complete_extraction_run(task_id, "failed", {"error": task.error_message})
        else:
            task.status = "failed"
            task.error_message = "No entities found to continue processing"
            metadata_store.complete_extraction_run(task_id, "failed", {"error": task.error_message})
            
    except Exception as e:
        logger.error(f"Error continuing extraction pipeline for task {task_id}: {e}")
        task = extraction_tasks.get(task_id)
        if task:
            task.status = "failed"
            task.error_message = str(e)
            metadata_store.complete_extraction_run(task_id, "failed", {"error": str(e)})

async def run_extraction_pipeline(
    task_id: str,
    file_path: str,
    extraction_config: Optional[dict[str, Any]],
    entity_extractor: EntityExtractor,
    ontology_mapper: OntologyMapper,
    neo4j_manager: Neo4jGraphManager,
    metadata_store: MetadataStore,
    relationship_discoverer: RelationshipDiscoverer,
    recommendation_service: Optional[RecommendationService] = None,
):
    """Run the complete extraction pipeline in the background."""
    task = extraction_tasks.get(task_id)
    if not task:
        return

    try:
        service = recommendation_service
        if service is None:
            try:
                service = get_recommendation_service()
            except Exception as service_error:
                logger.warning(
                    "Recommendation service unavailable for task %s: %s",
                    task_id,
                    service_error,
                )
                service = None

        if extraction_config is not None:
            task.extraction_config = extraction_config

        metadata_store.create_extraction_run(task_id, "processing", {"file_path": file_path})
        task.status = "processing"
        task.progress = 0.1
        try:
            await broadcast_task_update(
                task_id,
                task.status,
                message="Extraction task started",
                progress=int(task.progress * 100),
            )
        except Exception:
            pass

        logger.info(f"Profiling dataset for task {task_id}")
        dataset_profile = await profile_dataset(file_path, metadata_store)
        task.dataset_profile = dataset_profile
        task.progress = 0.2
        try:
            await broadcast_task_update(
                task_id,
                task.status,
                message="Dataset profiled",
                progress=int(task.progress * 100),
            )
        except Exception:
            pass

        logger.info(f"Extracting entities for task {task_id}")
        entities = await extract_entities(
            file_path, dataset_profile, extraction_config, entity_extractor
        )
        task.entities = entities
        task.progress = 0.5
        try:
            await broadcast_task_update(
                task_id,
                task.status,
                message="Entities extracted",
                progress=int(task.progress * 100),
            )
        except Exception:
            pass

        if service:
            try:
                entities_dict = [
                    entity.dict() if hasattr(entity, "dict") else entity
                    for entity in entities
                ]
                recommendations = await service.generate_recommendations(
                    task_id, entities_dict, dataset_profile.dict()
                )

                session = RecommendationSession(
                    task_id=task_id,
                    metadata=recommendations.get("rl_metadata", {}),
                )
                session.node_recommendations = [
                    _to_node_recommendation(candidate, session.id)
                    for candidate in recommendations.get("node_recommendations", [])
                ]
                session.edge_recommendations = [
                    _to_edge_recommendation(candidate, session.id)
                    for candidate in recommendations.get("edge_recommendations", [])
                ]

                if session.node_recommendations or session.edge_recommendations:
                    await metadata_store.create_recommendation_session(session)
                    task.recommendation_session = session
                    task.status = "awaiting_recommendations_approval"
                    task.progress = 0.6

                    try:
                        await broadcast_task_update(
                            task_id,
                            task.status,
                            message="Recommendations ready for human review",
                            progress=int(task.progress * 100),
                        )
                    except Exception:
                        pass

                    logger.info(
                        "Recommendations generated for task %s, awaiting human approval",
                        task_id,
                    )
                    return
                else:
                    logger.info(
                        "No LLM recommendations returned for task %s; falling back to heuristics",
                        task_id,
                    )

            except Exception as recommendation_error:
                logger.error(
                    "Failed to generate recommendations for task %s: %s",
                    task_id,
                    recommendation_error,
                )
                logger.warning(
                    "Continuing extraction pipeline without recommendations for task %s",
                    task_id,
                )

        if not service or not (task.recommendation_session and task.recommendation_session.node_recommendations):
            fallback_session = _build_fallback_recommendations(
                task_id,
                entities,
                dataset_profile,
            )
            if fallback_session:
                await metadata_store.create_recommendation_session(fallback_session)
                task.recommendation_session = fallback_session
                task.status = "awaiting_recommendations_approval"
                task.progress = 0.6

                try:
                    await broadcast_task_update(
                        task_id,
                        task.status,
                        message="Fallback recommendations ready for review",
                        progress=int(task.progress * 100),
                    )
                except Exception:
                    pass

                logger.info(
                    "Fallback recommendations generated for task %s", task_id
                )
                return

        logger.info(f"Discovering relationships for task {task_id}")
        relationships = await discover_relationships(
            entities,
            extraction_config,
            neo4j_manager,
            relationship_discoverer,
            file_path,
            dataset_profile.columns,
        )
        task.relationships = relationships
        task.progress = 0.8
        try:
            await broadcast_task_update(
                task_id,
                task.status,
                message="Relationships discovered",
                progress=int(task.progress * 100),
            )
        except Exception:
            pass

        logger.info(f"Mapping entities to ontologies for task {task_id}")
        ontology_results = await map_to_ontologies(
            entities, relationships, ontology_mapper
        )
        task.progress = 0.9
        try:
            await broadcast_task_update(
                task_id,
                task.status,
                message="Entities mapped to ontologies",
                progress=int(task.progress * 100),
            )
        except Exception:
            pass

        logger.info(f"Storing results in Neo4j for task {task_id}")
        
        entities_stored = 0
        relationships_stored = 0
        
        # Store entities
        for entity in entities:
            if not getattr(entity, "id", None):
                content = f"{entity.name}_{entity.entity_type}_{','.join(sorted(entity.source_columns))}"
                entity.id = f"entity_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"
            
            success = neo4j_manager.store_entity_with_metadata(
                entity=entity,
                source_file=task_id,  # Using task_id as source file identifier
                extraction_timestamp=datetime.utcnow(),
                version="1.0"
            )
            if success:
                entities_stored += 1
        
        # Store relationships
        for relationship in relationships:
            if not getattr(relationship, "id", None):
                content = (
                    f"{relationship.source_entity_id}_{relationship.target_entity_id}_"
                    f"{relationship.relationship_type}"
                )
                relationship.id = f"rel_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"

        try:
            await store_in_neo4j(
                entities, relationships, neo4j_manager, task_id, file_path
            )
        except Exception as storage_error:
            logger.error(f"Neo4j storage failed: {storage_error}")

        task.progress = 1.0

        metadata_store.complete_extraction_run(
            task_id,
            "completed",
            {
                "entities_count": len(entities),
                "relationships_count": len(relationships),
                "entities": [
                    entity.dict() if hasattr(entity, "dict") else entity.__dict__
                    for entity in entities
                ],
                "relationships": [
                    relationship.dict()
                    if hasattr(relationship, "dict")
                    else relationship.__dict__
                    for relationship in relationships
                ],
                "ontology_results": (
                    ontology_results.model_dump()
                    if hasattr(ontology_results, "model_dump")
                    else ontology_results
                ),
                "completed_at": datetime.now().isoformat(),
            },
        )

        task.status = "completed"
        task.completed_at = datetime.now()

        try:
            await broadcast_extraction_complete(
                task_id,
                {
                    "entities_count": len(entities),
                    "relationships_count": len(relationships),
                },
            )
            await broadcast_task_update(
                task_id,
                "completed",
                message="Extraction pipeline completed",
                progress=100,
            )
        except Exception:
            pass

        logger.info(f"Extraction pipeline completed for task {task_id}")

    except Exception as e:
        logger.error(f"Extraction pipeline failed for task {task_id}: {e}")
        task.status = "failed"
        task.errors.append(str(e))

        try:
            metadata_store.complete_extraction_run(
                task_id,
                "failed",
                {
                    "error": str(e),
                    "failed_at": datetime.now().isoformat(),
                },
            )
        except Exception as store_error:
            logger.error(
                f"Failed to update metadata store with failure status: {store_error}"
            )



async def profile_dataset(
    file_path: str, metadata_store: MetadataStore
) -> DatasetProfile:
    """Profile the uploaded dataset."""
    import pandas as pd
    from app.domain.models.entities import ColumnProfile, DataType

    try:
        # Read the CSV to get basic information
        df = pd.read_csv(file_path)

        # Create column profiles
        columns = []
        for col_name in df.columns:
            col_series = df[col_name]

            # Determine data type
            if pd.api.types.is_integer_dtype(col_series):
                data_type = DataType.INTEGER
            elif pd.api.types.is_float_dtype(col_series):
                data_type = DataType.FLOAT
            elif pd.api.types.is_bool_dtype(col_series):
                data_type = DataType.BOOLEAN
            elif pd.api.types.is_datetime64_any_dtype(col_series):
                data_type = DataType.DATETIME
            elif pd.api.types.is_numeric_dtype(col_series):
                data_type = DataType.NUMERICAL
            else:
                data_type = DataType.STRING

            # Create column profile
            column_profile = ColumnProfile(
                name=col_name,
                data_type=data_type,
                non_null_count=int(col_series.count()),
                null_count=int(col_series.isnull().sum()),
                unique_count=int(col_series.nunique()),
                sample_values=col_series.dropna().astype(str).head(10).tolist(),
                metadata={},
            )
            columns.append(column_profile)

        return DatasetProfile(
            file_path=file_path,
            row_count=len(df),
            column_count=len(df.columns),
            columns=columns,
            created_at=datetime.now().isoformat(),
            metadata={},
        )

    except Exception as e:
        logger.error(f"Failed to profile dataset {file_path}: {e}")
        # Return basic profile if profiling fails
        return DatasetProfile(
            file_path=file_path,
            row_count=0,
            column_count=0,
            columns=[],
            created_at=datetime.now().isoformat(),
            metadata={"error": str(e)},
        )


async def extract_entities(
    file_path: str,
    dataset_profile: DatasetProfile,
    extraction_config: Optional[dict[str, Any]],
    entity_extractor: EntityExtractor,
) -> list[Entity]:
    """Extract entities from the dataset."""
    config = extraction_config or {}

    # Use the actual entity extractor
    entities = entity_extractor.extract_entities(
        file_path=file_path, columns=dataset_profile.columns, config=config
    )

    return entities


async def map_to_ontologies(
    entities: list[Entity],
    relationships: list[Relationship],
    ontology_mapper: OntologyMapper,
) -> dict[str, Any]:
    """Map entities to standard ontologies."""
    # Use the actual ontology mapper
    mapping_results = ontology_mapper.map_entities_to_ontologies(
        entities, relationships
    )
    # Convert OntologyMappingResult to dictionary
    return mapping_results.model_dump()


async def discover_relationships(
    entities: list[Entity],
    extraction_config: Optional[dict[str, Any]],
    neo4j_manager: Neo4jGraphManager,
    relationship_discoverer: RelationshipDiscoverer,
    file_path: str,
    columns: list,
) -> list[Relationship]:
    """Discover relationships between entities."""
    logger.info(f"Starting relationship discovery for {len(entities)} entities")
    
    try:
        # Use the relationship discoverer to find relationships
        relationships = relationship_discoverer.discover_relationships(
            file_path=file_path,
            entities=entities,
            columns=columns,
            config=extraction_config or {},
        )
        
        logger.info(f"Discovered {len(relationships)} relationships")
        return relationships
        
    except Exception as e:
        logger.error(f"Error during relationship discovery: {e}")
        # Return empty list on error to not break the pipeline
        return []


async def store_in_neo4j(
    entities: list[Entity],
    relationships: list[Relationship],
    neo4j_manager: Neo4jGraphManager,
    task_id: str,
    file_path: str,
):
    """Store extracted entities and relationships in Neo4j."""
    logger.info(f"Starting Neo4j storage for {len(entities)} entities and {len(relationships)} relationships")
    
    try:
        # Ensure connection is established
        if not neo4j_manager.is_connected():
            logger.info("Neo4j not connected, attempting to connect...")
            success = neo4j_manager.connect()
            if not success:
                logger.error("Failed to connect to Neo4j")
                raise Exception("Cannot connect to Neo4j database")
            logger.info("Neo4j manager connected successfully")
        else:
            logger.info("Neo4j manager already connected")
        
        # Verify connection is working
        if not neo4j_manager.is_connected():
            logger.error("Neo4j connection verification failed")
            raise Exception("Neo4j connection verification failed")
        
        # Store entities
        entities_stored = 0
        logger.info(f"Starting to store {len(entities)} entities")
        for i, entity in enumerate(entities):
            try:
                logger.info(f"Processing entity {i+1}/{len(entities)}: {getattr(entity, 'name', 'NO_NAME')}")
                logger.info(f"Entity ID: {getattr(entity, 'id', 'NO_ID')}")
                logger.info(f"Entity type: {getattr(entity, 'entity_type', 'NO_TYPE')}")
                
                # Extract just the filename from the full path
                file_name = os.path.basename(file_path)
                
                success = neo4j_manager.store_entity_with_metadata(
                    entity=entity,
                    source_file=file_name,
                    extraction_timestamp=datetime.now(),
                    task_id=task_id,
                )
                if success:
                    logger.info(f"Successfully stored entity: {getattr(entity, 'name', 'NO_NAME')}")
                    entities_stored += 1
                else:
                    logger.error(f"Failed to store entity: {getattr(entity, 'name', 'NO_NAME')}")
            except Exception as e:
                logger.error(f"Error storing entity {getattr(entity, 'name', 'NO_NAME')}: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")

        # Store relationships
        relationships_stored = 0
        for relationship in relationships:
            try:
                success = neo4j_manager.store_relationship_with_metadata(
                    relationship=relationship,
                    discovered_at=datetime.now(),
                )
                if success:
                    logger.info(f"Successfully stored relationship: {getattr(relationship, 'id', 'NO_ID')}")
                    relationships_stored += 1
                else:
                    logger.error(f"Failed to store relationship: {getattr(relationship, 'id', 'NO_ID')}")
            except Exception as e:
                logger.error(f"Error storing relationship {getattr(relationship, 'id', 'NO_ID')}: {e}")
        
        logger.info(f"Neo4j storage completed: {entities_stored}/{len(entities)} entities, {relationships_stored}/{len(relationships)} relationships")

    except Exception as e:
        logger.error(f"Failed to store in Neo4j: {e}")
        logger.error(f"Storage error details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise


@router.get("/{task_id}", response_model=dict[str, Any])
async def get_extraction_status(task_id: str):
    """Get the status and results of an extraction task."""
    task = extraction_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "message": f"Task is {task.status}",
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "entities_count": len(task.entities),
        "relationships_count": len(task.relationships),
        "errors": task.errors,
        "entities": [entity.dict() if hasattr(entity, 'dict') else entity.__dict__ for entity in task.entities],
        "relationships": [rel.dict() if hasattr(rel, 'dict') else rel.__dict__ for rel in task.relationships],
    }


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get the current status of a specific task."""
    task = extraction_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "created_at": task.created_at.isoformat(),
    }


@router.post(
    "/{task_id}/generate-recommendations", response_model=RecommendationSession
)
async def generate_recommendations(
    task_id: str,
    background_tasks: BackgroundTasks,
    recommendation_service: Optional[RecommendationService] = Depends(
        get_recommendation_service
    ),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Generate recommendations for a given task."""
    task = extraction_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if recommendation_service is None:
        raise HTTPException(
            status_code=503,
            detail="Recommendation service is not available",
        )

    dataset_profile = task.dataset_profile or await profile_dataset(
        task.file_path, metadata_store
    )

    entities_dict = [
        entity.dict() if hasattr(entity, "dict") else entity for entity in task.entities
    ]

    recommendations = await recommendation_service.generate_recommendations(
        task_id, entities_dict, dataset_profile.dict()
    )

    session = RecommendationSession(
        task_id=task_id,
        metadata=recommendations.get("rl_metadata", {}),
    )
    session.node_recommendations = [
        _to_node_recommendation(node, session.id)
        for node in recommendations.get("node_recommendations", [])
    ]
    session.edge_recommendations = [
        _to_edge_recommendation(edge, session.id)
        for edge in recommendations.get("edge_recommendations", [])
    ]

    await metadata_store.create_recommendation_session(session)
    task.recommendation_session = session

    return session


@router.get("/{task_id}/recommendations", response_model=RecommendationSession)
async def get_recommendations(
    task_id: str,
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Get recommendations for a given task."""
    session = await metadata_store.get_recommendation_session(task_id)
    task = extraction_tasks.get(task_id)

    if not session and task and task.recommendation_session:
        session = task.recommendation_session

    if session and task and task.recommendation_session:
        if (
            not session.node_recommendations
            and task.recommendation_session.node_recommendations
        ):
            session.node_recommendations = (
                task.recommendation_session.node_recommendations
            )
        if (
            not session.edge_recommendations
            and task.recommendation_session.edge_recommendations
        ):
            session.edge_recommendations = (
                task.recommendation_session.edge_recommendations
            )

    if not session:
        entities: list[Entity] = []
        dataset_profile: Optional[DatasetProfile] = None

        if task:
            entities = list(task.entities or [])
            dataset_profile = task.dataset_profile
            if not dataset_profile and task.file_path:
                try:
                    dataset_profile = await profile_dataset(
                        task.file_path, metadata_store
                    )
                except Exception as profile_error:
                    logger.debug(
                        "Failed to rebuild dataset profile for task %s: %s",
                        task_id,
                        profile_error,
                    )

        if not entities:
            try:
                run_metadata = metadata_store.get_extraction_run(task_id)
            except Exception as run_error:
                logger.debug(
                    "Failed to load extraction run metadata for %s: %s",
                    task_id,
                    run_error,
                )
                run_metadata = None

            if run_metadata:
                payload = run_metadata.get("metadata") or {}
                raw_entities = payload.get("entities") or payload.get(
                    "ontology_results", {}
                ).get("unmapped_entities")
                if raw_entities:
                    for entity_payload in raw_entities:
                        try:
                            entities.append(Entity(**entity_payload))
                        except Exception as build_error:
                            logger.debug(
                                "Failed to rebuild entity for fallback recommendations: %s",
                                build_error,
                            )

        fallback_session = _build_fallback_recommendations(
            task_id,
            entities,
            dataset_profile,
        )
        if fallback_session:
            await metadata_store.create_recommendation_session(fallback_session)
            if task:
                task.recommendation_session = fallback_session
            session = fallback_session

    if not session:
        raise HTTPException(status_code=404, detail="Recommendations not found")

    return session


@router.post("/{task_id}/recommendations/feedback")
async def submit_recommendation_feedback(
    task_id: str,
    feedback: dict[str, Any],
    background_tasks: BackgroundTasks,
    ontology_mapper: OntologyMapper = Depends(get_ontology_mapper),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    relationship_discoverer: RelationshipDiscoverer = Depends(
        get_relationship_discoverer
    ),
    recommendation_service: Optional[RecommendationService] = Depends(
        get_recommendation_service
    ),
):
    """Submit feedback for recommendations and continue extraction pipeline."""
    try:
        logger.info(f"Received recommendation feedback for task {task_id}: {feedback}")

        task = extraction_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        session = task.recommendation_session or await metadata_store.get_recommendation_session(
            task_id
        )

        approved_overall = bool(feedback.get("approved", False))
        feedback_items = feedback.get("items", {}) or {}
        node_feedback_items = feedback_items.get("nodes", []) or []
        edge_feedback_items = feedback_items.get("edges", []) or []
        reviewer_notes = feedback.get("notes")

        node_updates_for_store: list[dict[str, Any]] = []
        edge_updates_for_store: list[dict[str, Any]] = []

        entity_map = {entity.id: entity for entity in task.entities if entity.id}

        approved_entity_ids: set[str] = set()
        for node_item in node_feedback_items:
            node_id = str(node_item.get("id")) if node_item.get("id") else None
            if not node_id:
                continue

            final_name = (
                node_item.get("finalName")
                or node_item.get("name")
                or node_item.get("label")
            )
            entity_type = (
                node_item.get("entityType")
                or node_item.get("entity_type")
                or "unknown"
            )
            confidence = node_item.get("confidence")
            source_columns = (
                node_item.get("sourceColumns")
                or node_item.get("source_columns")
                or []
            )
            metadata_payload = node_item.get("metadata") or {}
            linked_entity_id = (
                node_item.get("linkedEntityId")
                or node_item.get("entityId")
                or metadata_payload.get("entity_id")
            )
            decision = node_item.get("decision") or (
                "approved" if node_item.get("approved", approved_overall) else "rejected"
            )

            entity = entity_map.get(linked_entity_id)
            if entity:
                if final_name:
                    entity.name = final_name
                if entity_type:
                    entity.entity_type = entity_type
                if confidence is not None:
                    entity.confidence = float(confidence)
                if source_columns:
                    entity.source_columns = list(source_columns)
                if metadata_payload.get("attributes"):
                    entity.attributes.update(metadata_payload["attributes"])
                if metadata_payload.get("source_value"):
                    entity.source_value = metadata_payload["source_value"]
            else:
                new_entity = Entity(
                    id=str(uuid.uuid4()),
                    name=final_name or "Human Approved Entity",
                    entity_type=entity_type,
                    confidence=float(confidence or 0.75),
                    source_columns=list(source_columns),
                    attributes=metadata_payload.get("attributes", {}),
                    source_value=metadata_payload.get("source_value"),
                )
                task.entities.append(new_entity)
                entity_map[new_entity.id] = new_entity
                linked_entity_id = new_entity.id

            node_updates_for_store.append(
                {
                    "id": node_id,
                    "name": final_name,
                    "entity_type": entity_type,
                    "confidence": confidence,
                    "source_columns": list(source_columns) if source_columns else None,
                    "decision": decision,
                    "metadata": {
                        "human_feedback": {
                            "entity_id": linked_entity_id,
                            "attributes": metadata_payload.get("attributes", {}),
                            "source_value": metadata_payload.get("source_value"),
                            "notes": reviewer_notes,
                        }
                    },
                }
            )

            if decision == "approved" and linked_entity_id:
                approved_entity_ids.add(str(linked_entity_id))

        relationship_map = {
            rel.id: rel for rel in task.relationships if getattr(rel, "id", None)
        }

        approved_relationship_ids: set[str] = set()
        for edge_item in edge_feedback_items:
            edge_id = str(edge_item.get("id")) if edge_item.get("id") else None
            if not edge_id:
                continue

            relationship_type = (
                edge_item.get("relationshipType")
                or edge_item.get("relationship_type")
                or "RELATED_TO"
            )
            confidence = edge_item.get("confidence")
            metadata_payload = edge_item.get("metadata") or {}
            decision = edge_item.get("decision") or (
                "approved" if edge_item.get("approved", approved_overall) else "rejected"
            )

            source_entity_id = (
                edge_item.get("sourceEntityId")
                or edge_item.get("source_entity_id")
                or metadata_payload.get("source_entity_id")
                or edge_item.get("sourceNodeId")
            )
            target_entity_id = (
                edge_item.get("targetEntityId")
                or edge_item.get("target_entity_id")
                or metadata_payload.get("target_entity_id")
                or edge_item.get("targetNodeId")
            )

            relationship = relationship_map.get(edge_id)
            if relationship:
                relationship.relationship_type = relationship_type
                if confidence is not None:
                    relationship.confidence = float(confidence)
                if metadata_payload.get("attributes"):
                    relationship.attributes.update(metadata_payload["attributes"])
                if metadata_payload.get("source_columns"):
                    relationship.source_columns = metadata_payload["source_columns"]
            else:
                relationship = Relationship(
                    id=edge_id,
                    source_entity_id=str(source_entity_id) if source_entity_id else None,
                    target_entity_id=str(target_entity_id) if target_entity_id else None,
                    relationship_type=relationship_type,
                    confidence=float(confidence or 0.7),
                    attributes=metadata_payload.get("attributes", {}),
                    source_columns=metadata_payload.get("source_columns", []),
                )
                task.relationships.append(relationship)
                relationship_map[relationship.id] = relationship

            edge_updates_for_store.append(
                {
                    "id": relationship.id,
                    "relationship_type": relationship_type,
                    "confidence": confidence,
                    "decision": decision,
                    "reasoning": metadata_payload.get("reasoning"),
                    "metadata": {
                        "human_feedback": {
                            "source_entity_id": relationship.source_entity_id,
                            "target_entity_id": relationship.target_entity_id,
                            "attributes": metadata_payload.get("attributes", {}),
                            "notes": reviewer_notes,
                        }
                    },
                }
            )

            if decision == "approved":
                approved_relationship_ids.add(str(relationship.id))

        if recommendation_service:
            try:
                await recommendation_service.process_recommendation_feedback(
                    task_id, feedback
                )
            except Exception as exc:
                logger.error("Error processing RL feedback: %s", exc)

        status_label = "approved" if approved_overall else "rejected"

        await metadata_store.update_recommendation_feedback(
            task_id,
            status_label,
            feedback,
            node_updates_for_store,
            edge_updates_for_store,
        )

        if session:
            session.status = status_label
            session.approved_at = datetime.now()
            session.metadata = {**(session.metadata or {}), "last_feedback": feedback}
            node_map = {str(node.id): node for node in session.node_recommendations}
            for update in node_updates_for_store:
                node_obj = node_map.get(update.get("id"))
                if not node_obj:
                    continue
                if update.get("name"):
                    node_obj.recommended_name = update["name"]
                if update.get("entity_type"):
                    node_obj.entity_type = update["entity_type"]
                if update.get("confidence") is not None:
                    node_obj.confidence_score = float(update["confidence"])
                if update.get("source_columns"):
                    node_obj.source_columns = update["source_columns"]
                node_obj.user_feedback = update.get("decision")
                node_obj.llm_metadata = node_obj.llm_metadata or {}
                node_obj.llm_metadata.setdefault("human_feedback", {}).update(
                    update.get("metadata", {}).get("human_feedback", {})
                )

            edge_map = {str(edge.id): edge for edge in session.edge_recommendations}
            for update in edge_updates_for_store:
                edge_obj = edge_map.get(update.get("id"))
                if not edge_obj:
                    continue
                if update.get("relationship_type"):
                    edge_obj.relationship_type = update["relationship_type"]
                if update.get("confidence") is not None:
                    edge_obj.confidence_score = float(update["confidence"])
                if update.get("reasoning"):
                    edge_obj.reasoning = update["reasoning"]
                edge_obj.user_feedback = update.get("decision")
                edge_obj.connection_evidence = edge_obj.connection_evidence or {}
                edge_obj.connection_evidence.setdefault(
                    "human_feedback", {}
                ).update(update.get("metadata", {}).get("human_feedback", {}))

            task.recommendation_session = session

        approved_entities = [
            entity_map.get(entity_id)
            for entity_id in approved_entity_ids
            if entity_map.get(entity_id)
        ]

        approved_relationships = [
            relationship_map.get(rel_id)
            for rel_id in approved_relationship_ids
            if relationship_map.get(rel_id)
        ]

        try:
            _persist_entities_feedback(
                neo4j_manager,
                [entity for entity in approved_entities if entity],
                task_id,
                getattr(task, "file_path", None),
            )
            _persist_relationships_feedback(
                neo4j_manager,
                [rel for rel in approved_relationships if rel],
            )
        except Exception as persist_error:
            logger.error(
                "Failed to persist approved recommendations for task %s: %s",
                task_id,
                persist_error,
            )

        try:
            metadata_store.complete_extraction_run(
                task_id,
                task.status or "processing",
                {
                    "entities_count": len(task.entities),
                    "relationships_count": len(task.relationships),
                    "entities": [
                        entity.dict() if hasattr(entity, "dict") else entity.__dict__
                        for entity in task.entities
                    ],
                    "relationships": [
                        rel.dict() if hasattr(rel, "dict") else rel.__dict__
                        for rel in task.relationships
                    ],
                    "updated_at": datetime.now().isoformat(),
                },
            )
        except Exception as refresh_error:
            logger.error(
                "Failed to refresh extraction run metadata for task %s: %s",
                task_id,
                refresh_error,
            )

        try:
            await broadcast_task_update(
                task_id,
                "processing",
                message="Human feedback received. Resuming ontology pipeline.",
                progress=int((task.progress or 0.6) * 100),
            )
        except Exception:
            pass

        background_tasks.add_task(
            continue_extraction_pipeline,
            task_id,
            task.extraction_config or {},
            ontology_mapper,
            neo4j_manager,
            metadata_store,
            relationship_discoverer,
        )

        return {
            "status": "feedback received, RL model updated, continuing extraction",
            "nodes_processed": len(node_updates_for_store),
            "edges_processed": len(edge_updates_for_store),
        }

    except Exception as e:
        logger.error(f"Error in submit_recommendation_feedback: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process feedback: {str(e)}"
        )
