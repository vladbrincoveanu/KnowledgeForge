"""Ontology extraction endpoints."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import tempfile
import logging
import asyncio

from pydantic import BaseModel, Field

# Import actual backend services
from ....services.entity_extraction.entity_extractor import EntityExtractor
from ....services.ontology_mapping.ontology_mapper import OntologyMapper
from ....services.relationship_discovery.relationship_discoverer import RelationshipDiscoverer
from ....infrastructure.graph.neo4j_manager import Neo4jGraphManager
from ....infrastructure.storage.metadata_store import MetadataStore
from ....domain.models.entities import DatasetProfile, Entity, Relationship
from ....utils.config import get_config

logger = logging.getLogger(__name__)

class ExtractionResponse(BaseModel):
    """Response model for extraction operations."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

class ExtractionTask:
    """Manages extraction task state and progress."""
    
    def __init__(self, task_id: str, file_path: str):
        self.task_id = task_id
        self.file_path = file_path
        self.status = "pending"
        self.progress = 0.0
        self.entities: List[Entity] = []
        self.relationships: List[Relationship] = []
        self.errors: List[str] = []
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None

# In-memory task storage (replace with Redis/database in production)
extraction_tasks: Dict[str, ExtractionTask] = {}

router = APIRouter(prefix="/extract", tags=["extraction"])

# Dependency injection
def get_entity_extractor():
    """Get entity extractor instance."""
    config = get_config()
    return EntityExtractor(
        cache_dir=config.extraction.cache_dir if hasattr(config.extraction, 'cache_dir') else None
    )

def get_ontology_mapper():
    """Get ontology mapper instance."""
    config = get_config()
    return OntologyMapper(
        cache_dir=config.extraction.cache_dir if hasattr(config.extraction, 'cache_dir') else None
    )

def get_neo4j_manager():
    """Get Neo4j manager instance."""
    config = get_config()
    return Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database
    )

def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config.metadata_storage.duckdb_path)

@router.post("/upload", response_model=Dict[str, Any])
async def upload_csv_file(
    file: UploadFile = File(...),
    metadata_store: MetadataStore = Depends(get_metadata_store)
):
    """
    Upload a CSV file for processing.
    
    This endpoint accepts CSV files and stores them for ontology extraction.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received")
    
    try:
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
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
            "status": "uploaded"
        }
        
        # Store in metadata store
        await metadata_store.store_file_metadata(file_metadata)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": file_path,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "message": "File uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@router.post("/", response_model=ExtractionResponse)
async def extract_ontology(
    file_path: str,
    background_tasks: BackgroundTasks,
    extraction_config: Optional[Dict[str, Any]] = None,
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
    ontology_mapper: OntologyMapper = Depends(get_ontology_mapper),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store)
):
    """
    Process CSV file and extract ontology.
    
    This endpoint starts an asynchronous ontology extraction process.
    Use the returned task_id to track progress via GET /extract/{task_id}.
    """
    try:
        # Validate that the file exists
        if not Path(file_path).exists():
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create extraction task
        task = ExtractionTask(task_id, file_path)
        extraction_tasks[task_id] = task
        
        # Add background task for extraction
        background_tasks.add_task(
            run_extraction_pipeline,
            task_id,
            file_path,
            extraction_config,
            entity_extractor,
            ontology_mapper,
            neo4j_manager,
            metadata_store
        )
        
        return ExtractionResponse(
            task_id=task_id,
            status="pending",
            message="Extraction task created and queued",
            created_at=datetime.now(),
            estimated_completion=datetime.now() + timedelta(minutes=5)
        )
        
    except Exception as e:
        logger.error(f"Failed to create extraction task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create extraction task: {str(e)}")

async def run_extraction_pipeline(
    task_id: str,
    file_path: str,
    extraction_config: Optional[Dict[str, Any]],
    entity_extractor: EntityExtractor,
    ontology_mapper: OntologyMapper,
    neo4j_manager: Neo4jGraphManager,
    metadata_store: MetadataStore
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
        entities = await extract_entities(file_path, dataset_profile, extraction_config, entity_extractor)
        task.entities = entities
        task.progress = 0.5
        
        # Step 3: Map to ontologies
        logger.info(f"Mapping entities to ontologies for task {task_id}")
        ontology_results = await map_to_ontologies(entities, ontology_mapper)
        task.progress = 0.7
        
        # Step 4: Discover relationships
        logger.info(f"Discovering relationships for task {task_id}")
        relationships = await discover_relationships(entities, extraction_config, neo4j_manager)
        task.relationships = relationships
        task.progress = 0.9
        
        # Step 5: Store in Neo4j
        logger.info(f"Storing results in Neo4j for task {task_id}")
        await store_in_neo4j(entities, relationships, neo4j_manager)
        task.progress = 1.0
        
        # Step 6: Update metadata store
        await metadata_store.store_extraction_results(task_id, {
            "entities_count": len(entities),
            "relationships_count": len(relationships),
            "ontology_results": ontology_results,
            "completed_at": datetime.now().isoformat()
        })
        
        task.status = "completed"
        task.completed_at = datetime.now()
        
        logger.info(f"Extraction pipeline completed for task {task_id}")
        
    except Exception as e:
        logger.error(f"Extraction pipeline failed for task {task_id}: {e}")
        task.status = "failed"
        task.errors.append(str(e))

async def profile_dataset(file_path: str, metadata_store: MetadataStore) -> DatasetProfile:
    """Profile the uploaded dataset."""
    # This would use your data profiling service
    # For now, return a basic profile
    return DatasetProfile(
        file_path=file_path,
        row_count=0,  # Would be calculated
        column_count=0,  # Would be calculated
        columns=[],  # Would be populated
        created_at=datetime.now().isoformat(),
        metadata={}
    )

async def extract_entities(
    file_path: str,
    dataset_profile: DatasetProfile,
    extraction_config: Optional[Dict[str, Any]],
    entity_extractor: EntityExtractor
) -> List[Entity]:
    """Extract entities from the dataset."""
    config = extraction_config or {}
    
    # Use the actual entity extractor
    entities = entity_extractor.extract_entities(
        file_path=file_path,
        columns=dataset_profile.columns,
        config=config
    )
    
    return entities

async def map_to_ontologies(
    entities: List[Entity],
    ontology_mapper: OntologyMapper
) -> Dict[str, Any]:
    """Map entities to standard ontologies."""
    # Use the actual ontology mapper
    mapping_results = ontology_mapper.map_entities_to_ontologies(entities)
    return mapping_results

async def discover_relationships(
    entities: List[Entity],
    extraction_config: Optional[Dict[str, Any]],
    neo4j_manager: Neo4jGraphManager
) -> List[Relationship]:
    """Discover relationships between entities."""
    # This would use your relationship discovery service
    # For now, return empty list
    return []

async def store_in_neo4j(
    entities: List[Entity],
    relationships: List[Relationship],
    neo4j_manager: Neo4jGraphManager
):
    """Store extracted entities and relationships in Neo4j."""
    try:
        with neo4j_manager:
            # Store entities
            for entity in entities:
                neo4j_manager.create_entity(entity)
            
            # Store relationships
            for relationship in relationships:
                neo4j_manager.create_relationship(relationship)
                
    except Exception as e:
        logger.error(f"Failed to store in Neo4j: {e}")
        raise

@router.get("/{task_id}", response_model=Dict[str, Any])
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
        "errors": task.errors
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
        "created_at": task.created_at.isoformat()
    }
