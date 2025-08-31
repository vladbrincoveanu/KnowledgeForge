"""Ontology extraction endpoints."""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.domain.models.entities import DatasetProfile, Entity, Relationship
from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.storage.metadata_store import (
    AdvancedMetadataStore as MetadataStore,
)

# Import actual backend services
from app.services.entity_extraction.entity_extractor import EntityExtractor
from app.services.ontology_mapping.ontology_mapper import OntologyMapper
from utils.config import get_config

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


# In-memory task storage (replace with Redis/database in production)
extraction_tasks: dict[str, ExtractionTask] = {}

router = APIRouter(prefix="/extract", tags=["extraction"])


# Dependency injection
def get_entity_extractor():
    """Get entity extractor instance."""
    config = get_config()
    return EntityExtractor(
        cache_dir=(
            config.extraction.cache_dir
            if hasattr(config.extraction, "cache_dir")
            else None
        )
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
    return Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database,
    )


def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config.metadata_storage.duckdb_path)


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
            metadata=file_metadata,
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


@router.post("/", response_model=ExtractionResponse)
async def extract_ontology(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
    ontology_mapper: OntologyMapper = Depends(get_ontology_mapper),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
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


async def run_extraction_pipeline(
    task_id: str,
    file_path: str,
    extraction_config: Optional[dict[str, Any]],
    entity_extractor: EntityExtractor,
    ontology_mapper: OntologyMapper,
    neo4j_manager: Neo4jGraphManager,
    metadata_store: MetadataStore,
):
    """Run the complete extraction pipeline in the background."""
    task = extraction_tasks.get(task_id)
    if not task:
        return

    try:
        task.status = "processing"
        task.progress = 0.1

        # Step 1: Profile the dataset
        logger.info(f"Profiling dataset for task {task_id}")
        dataset_profile = await profile_dataset(file_path, metadata_store)
        task.progress = 0.2

        # Step 2: Extract entities
        logger.info(f"Extracting entities for task {task_id}")
        entities = await extract_entities(
            file_path, dataset_profile, extraction_config, entity_extractor
        )
        task.entities = entities
        task.progress = 0.5

        # Step 3: Discover relationships
        logger.info(f"Discovering relationships for task {task_id}")
        relationships = await discover_relationships(
            entities, extraction_config, neo4j_manager
        )
        task.relationships = relationships
        task.progress = 0.7

        # Step 4: Map to ontologies
        logger.info(f"Mapping entities to ontologies for task {task_id}")
        ontology_results = await map_to_ontologies(
            entities, relationships, ontology_mapper
        )
        task.progress = 0.9

        # Step 5: Store in Neo4j
        logger.info(f"Storing results in Neo4j for task {task_id}")
        await store_in_neo4j(entities, relationships, neo4j_manager)
        task.progress = 1.0

        # Step 6: Update metadata store
        # Get the file_id from the task
        metadata_store.complete_extraction_run(
            task_id,
            {
                "entities_count": len(entities),
                "relationships_count": len(relationships),
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

        logger.info(f"Extraction pipeline completed for task {task_id}")

    except Exception as e:
        logger.error(f"Extraction pipeline failed for task {task_id}: {e}")
        task.status = "failed"
        task.errors.append(str(e))


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
    return mapping_results


async def discover_relationships(
    entities: list[Entity],
    extraction_config: Optional[dict[str, Any]],
    neo4j_manager: Neo4jGraphManager,
) -> list[Relationship]:
    """Discover relationships between entities."""
    # This would use your relationship discovery service
    # For now, return empty list
    return []


async def store_in_neo4j(
    entities: list[Entity],
    relationships: list[Relationship],
    neo4j_manager: Neo4jGraphManager,
):
    """Store extracted entities and relationships in Neo4j."""
    try:
        with neo4j_manager:
            # Store entities
            for entity in entities:
                neo4j_manager.store_entity_with_metadata(
                    entity=entity,
                    source_file="extraction_pipeline",  # Could be parameterized
                    extraction_timestamp=datetime.now(),
                )

            # Store relationships
            for relationship in relationships:
                neo4j_manager.store_relationship_with_metadata(
                    relationship=relationship,
                    discovered_at=datetime.now(),
                )

    except Exception as e:
        logger.error(f"Failed to store in Neo4j: {e}")
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
