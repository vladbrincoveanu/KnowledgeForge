"""
FastAPI application for ontology extraction service.

This module provides a comprehensive REST API for:
- CSV file processing and ontology extraction
- Entity and relationship management
- User feedback collection
- Graph visualization
- System metrics and health checks
- Real-time extraction progress via WebSocket
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect, status, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import uvicorn
import tempfile
import os

# Import ontology extraction components
from ontology_extractor import (
    DataProfiler,
    EntityExtractor,
    RelationshipDiscoverer,
    OntologyMapper,
    Neo4jGraphManager,
    LLMManager,
    QualityAssurance,
    ActiveLearningModule,
    MetadataStore,
    EmbeddingManager
)
from ontology_extractor.models import Entity, Relationship, Ontology, ExtractionConfig
from ontology_extractor.config import load_config, OntologyExtractionConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="KnowledgeForge Ontology Extraction API",
    description="Semantic ontology extraction from CSV files with local LLM support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Security
security = HTTPBearer(auto_error=False)

# Global state
extraction_tasks: Dict[str, Dict[str, Any]] = {}
websocket_connections: List[WebSocket] = []
config: Optional[OntologyExtractionConfig] = None
uploaded_files: Dict[str, str] = {}  # Map task_id to file_path for cleanup

def convert_numpy_types(value: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    import numpy as np
    
    # Handle None
    if value is None:
        return None
    
    # Handle numpy types
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.bool_):
        return bool(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, np.dtype):
        return str(value)
    elif isinstance(value, np.number):  # Catch any other numpy numeric types
        try:
            return value.item()
        except:
            return str(value)
    
    # Handle dictionaries - convert both keys and values
    elif isinstance(value, dict):
        converted_dict = {}
        for k, v in value.items():
            # Convert key if it's a numpy type
            if isinstance(k, np.dtype):
                converted_key = str(k)
            elif isinstance(k, np.integer):
                converted_key = int(k)
            elif isinstance(k, np.floating):
                converted_key = float(k)
            elif isinstance(k, np.bool_):
                converted_key = bool(k)
            else:
                converted_key = k
            
            # Convert value
            converted_value = convert_numpy_types(v)
            converted_dict[converted_key] = converted_value
        return converted_dict
    
    # Handle lists and tuples
    elif isinstance(value, (list, tuple)):
        return [convert_numpy_types(item) for item in value]
    
    # Handle pandas objects
    elif hasattr(value, 'dtype'):  # Handle pandas Series, DataFrames, etc.
        try:
            if hasattr(value, 'tolist'):
                return convert_numpy_types(value.tolist())
            elif hasattr(value, 'item'):
                return value.item()
            else:
                return str(value)
        except:
            return str(value)
    
    # Handle any object with item() method (scalar numpy types)
    elif hasattr(value, 'item'):
        try:
            return convert_numpy_types(value.item())
        except:
            return str(value)
    
    # Handle datetime objects
    elif hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except:
            return str(value)
    
    # For any other type, try to convert to string as fallback
    else:
        try:
            # Test if it's JSON serializable
            import json
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

def safe_serialize(obj: Any) -> Any:
    """Safely serialize any object, converting problematic types to strings."""
    try:
        # First try the numpy conversion
        converted = convert_numpy_types(obj)
        
        # Test JSON serialization
        import json
        json.dumps(converted)
        return converted
        
    except Exception as e:
        # If all else fails, convert to string representation
        logger.warning(f"Failed to serialize object: {e}, converting to string")
        return str(obj)

# Pydantic models for API requests/responses
class CSVUploadRequest(BaseModel):
    """Request model for CSV file upload."""
    file_path: str = Field(..., description="Path to CSV file")
    extraction_config: Optional[ExtractionConfig] = Field(default=None, description="Extraction configuration")
    
    # Remove the problematic validator that checks file existence during Pydantic validation
    # This was causing 422 errors because the validator runs before the request reaches the endpoint

class ExtractionResponse(BaseModel):
    """Response model for extraction operations."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

class EntityResponse(BaseModel):
    """Response model for entity data."""
    entities: List[Entity] = Field(..., description="List of extracted entities")
    total_count: int = Field(..., description="Total number of entities")
    extraction_metadata: Dict[str, Any] = Field(..., description="Extraction metadata")

class RelationshipResponse(BaseModel):
    """Response model for relationship data."""
    relationships: List[Relationship] = Field(..., description="List of discovered relationships")
    total_count: int = Field(..., description="Total number of relationships")
    discovery_metadata: Dict[str, Any] = Field(..., description="Discovery metadata")

class FeedbackRequest(BaseModel):
    """Request model for user feedback."""
    entity_id: Optional[str] = Field(None, description="Entity ID for feedback")
    relationship_id: Optional[str] = Field(None, description="Relationship ID for feedback")
    feedback_type: str = Field(..., description="Type of feedback")
    feedback_value: str = Field(..., description="Feedback value")
    confidence_delta: float = Field(..., ge=-1.0, le=1.0, description="Confidence adjustment")
    user_id: Optional[str] = Field(None, description="User identifier")

class GraphVisualizationResponse(BaseModel):
    """Response model for graph visualization."""
    cypher_queries: List[str] = Field(..., description="Cypher queries for visualization")
    graph_metadata: Dict[str, Any] = Field(..., description="Graph metadata")
    node_count: int = Field(..., description="Total number of nodes")
    edge_count: int = Field(..., description="Total number of edges")

class MetricsResponse(BaseModel):
    """Response model for system metrics."""
    system_metrics: Dict[str, Any] = Field(..., description="System performance metrics")
    extraction_metrics: Dict[str, Any] = Field(..., description="Extraction performance metrics")
    quality_metrics: Dict[str, Any] = Field(..., description="Quality assurance metrics")
    timestamp: datetime = Field(..., description="Metrics timestamp")

class HealthResponse(BaseModel):
    """Response model for health checks."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="API version")
    dependencies: Dict[str, str] = Field(..., description="Dependency status")

# Dependency functions
async def get_config() -> OntologyExtractionConfig:
    """Get configuration instance."""
    if config is None:
        raise HTTPException(status_code=500, detail="Configuration not initialized")
    return config

async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> bool:
    """Verify API key for authentication."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # In production, validate against stored API keys
    # For now, accept any non-empty token
    if not credentials.credentials or len(credentials.credentials) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True

# Background task for ontology extraction
async def run_ontology_extraction(
    task_id: str,
    file_path: str,
    extraction_config: Optional[ExtractionConfig] = None
):
    """Run ontology extraction in background."""
    try:
        logger.info(f"Starting extraction task {task_id} for file {file_path}")
        print(f"Starting extraction task {task_id} for file {file_path}")
        
        # Update task status
        extraction_tasks[task_id]["status"] = "processing"
        extraction_tasks[task_id]["started_at"] = datetime.now()
        
        # Notify WebSocket clients
        await broadcast_progress(task_id, "started", "Extraction started")
        
        # Initialize components
        logger.info(f"Initializing components for task {task_id}")
        config = await get_config()
        
        # Initialize LLM manager
        logger.info(f"Initializing LLM manager for task {task_id}")
        llm_manager = LLMManager(
            lmstudio_url=config.lmstudio.base_url,
            default_model=config.lmstudio.model_name
        )
        
        # Initialize other components
        logger.info(f"Initializing other components for task {task_id}")
        profiler = DataProfiler()
        entity_extractor = EntityExtractor(llm_manager=llm_manager)
        relationship_discoverer = RelationshipDiscoverer(llm_manager=llm_manager)
        ontology_mapper = OntologyMapper(llm_manager=llm_manager)
        
        # Step 1: Profile the data
        logger.info(f"Starting data profiling for task {task_id}")
        await broadcast_progress(task_id, "profiling", "Profiling dataset...")
        try:
            profile = profiler.profile_dataset(file_path)
            logger.info(f"Data profiling completed for task {task_id}")
        except Exception as e:
            logger.error(f"Data profiling failed for task {task_id}: {str(e)}")
            raise Exception(f"Data profiling failed: {str(e)}")
        
        # Step 2: Extract entities
        logger.info(f"Starting entity extraction for task {task_id}")
        await broadcast_progress(task_id, "extracting_entities", "Extracting entities...")
        try:
            entities = entity_extractor.extract_entities(
                file_path,
                profile.columns,
                extraction_config.dict() if extraction_config else {}
            )
            logger.info(f"Entity extraction completed for task {task_id}: {len(entities)} entities")
        except Exception as e:
            logger.error(f"Entity extraction failed for task {task_id}: {str(e)}")
            raise Exception(f"Entity extraction failed: {str(e)}")
        
        # Step 3: Discover relationships
        logger.info(f"Starting relationship discovery for task {task_id}")
        await broadcast_progress(task_id, "discovering_relationships", "Discovering relationships...")
        try:
            relationships = relationship_discoverer.discover_relationships(
                file_path,
                entities,
                profile.columns,
                extraction_config.dict() if extraction_config else {}
            )
            logger.info(f"Relationship discovery completed for task {task_id}: {len(relationships)} relationships")
        except Exception as e:
            logger.error(f"Relationship discovery failed for task {task_id}: {str(e)}")
            raise Exception(f"Relationship discovery failed: {str(e)}")
        
        # Step 4: Map to ontologies
        logger.info(f"Starting ontology mapping for task {task_id}")
        await broadcast_progress(task_id, "mapping_ontologies", "Mapping to standard ontologies...")
        try:
            mapping_result = ontology_mapper.map_entities_to_ontologies(entities, relationships)
            logger.info(f"Ontology mapping completed for task {task_id}")
        except Exception as e:
            logger.error(f"Ontology mapping failed for task {task_id}: {str(e)}")
            raise Exception(f"Ontology mapping failed: {str(e)}")
        
        # Store results
        logger.info(f"Storing results for task {task_id}")
        
        # Convert and store entities
        try:
            converted_entities = [convert_numpy_types(entity.dict()) for entity in entities]
            logger.info(f"Converted {len(converted_entities)} entities")
        except Exception as e:
            logger.error(f"Error converting entities: {e}")
            converted_entities = []
        
        # Convert and store relationships
        try:
            converted_relationships = [convert_numpy_types(rel.dict()) for rel in relationships]
            logger.info(f"Converted {len(converted_relationships)} relationships")
        except Exception as e:
            logger.error(f"Error converting relationships: {e}")
            converted_relationships = []
        
        # Convert and store mapping result
        try:
            converted_mapping = convert_numpy_types(mapping_result.dict())
            logger.info("Converted mapping result")
        except Exception as e:
            logger.error(f"Error converting mapping result: {e}")
            converted_mapping = {}
        
        # Convert and store profile
        try:
            converted_profile = convert_numpy_types(profile.dict())
            logger.info("Converted profile")
        except Exception as e:
            logger.error(f"Error converting profile: {e}")
            converted_profile = {}
        
        extraction_tasks[task_id]["results"] = {
            "entities": converted_entities,
            "relationships": converted_relationships,
            "mapping_result": converted_mapping,
            "profile": converted_profile
        }
        
        # Update task status
        extraction_tasks[task_id]["status"] = "completed"
        extraction_tasks[task_id]["completed_at"] = datetime.now()
        extraction_tasks[task_id]["processing_time"] = (
            extraction_tasks[task_id]["completed_at"] - 
            extraction_tasks[task_id]["started_at"]
        ).total_seconds()
        
        await broadcast_progress(task_id, "completed", "Extraction completed successfully")
        logger.info(f"Extraction task {task_id} completed successfully")
        print(f"Extraction task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Extraction task {task_id} failed: {str(e)}")
        print(f"Extraction task {task_id} failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Traceback: {traceback.format_exc()}")
        
        extraction_tasks[task_id]["status"] = "failed"
        extraction_tasks[task_id]["error"] = str(e)
        extraction_tasks[task_id]["completed_at"] = datetime.now()
        await broadcast_progress(task_id, "failed", f"Extraction failed: {str(e)}")

async def broadcast_progress(task_id: str, status: str, message: str):
    """Broadcast progress updates to WebSocket clients."""
    if websocket_connections:
        progress_data = {
            "task_id": task_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all connected clients
        for connection in websocket_connections[:]:  # Copy list to avoid modification during iteration
            try:
                await connection.send_json(progress_data)
            except WebSocketDisconnect:
                websocket_connections.remove(connection)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                websocket_connections.remove(connection)

# API Endpoints

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify API is working."""
    return {"message": "API is working", "timestamp": datetime.now().isoformat()}



@app.get("/config")
async def get_current_config():
    """Get the current configuration being used by the API."""
    try:
        config = await get_config()
        return {
            "lmstudio": {
                "base_url": config.lmstudio.base_url,
                "model_name": config.lmstudio.model_name,
                "use_embeddings": config.lmstudio.use_embeddings
            },
            "extraction": {
                "confidence_threshold": config.extraction.confidence_threshold,
                "max_entities_per_column": config.extraction.max_entities_per_column
            },
            "environment": config.environment,
            "debug": config.debug
        }
    except Exception as e:
        logger.error(f"Failed to get configuration: {str(e)}")
        return {"error": str(e)}

@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get the current status of a specific task."""
    if task_id not in extraction_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = extraction_tasks[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "message": task.get("message", ""),
        "error": task.get("error"),
        "created_at": task["created_at"],
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
        "processing_time": task.get("processing_time"),
        "has_results": "results" in task and task["results"] is not None
    }

@app.post("/test-upload")
async def test_upload(file: UploadFile = File(...)):
    """Minimal test upload endpoint to debug file upload issues."""
    print(f"TEST UPLOAD CALLED - File: {file.filename if file else 'None'}")
    return {"filename": file.filename, "size": file.size if hasattr(file, 'size') else 'Unknown'}

@app.post("/upload", response_model=Dict[str, Any])
async def upload_csv_file(
    file: UploadFile = File(...)
    # Temporarily disabled API key requirement to debug 422 error
    # _: bool = Depends(verify_api_key)
):
    """
    Upload a CSV file for processing.
    
    This endpoint accepts CSV files and stores them temporarily for ontology extraction.
    """
    print(f"UPLOAD ENDPOINT CALLED - File: {file.filename if file else 'None'}")
    logger.info(f"Upload endpoint called with file: {file.filename if file else 'None'}")
    logger.info(f"File details - Name: {file.filename}, Size: {file.size if hasattr(file, 'size') else 'Unknown'}, Type: {file.content_type}")
    logger.info(f"Request headers: {file.headers if hasattr(file, 'headers') else 'No headers'}")
    
    # Check if file object is valid
    if not file:
        logger.error("No file received")
        raise HTTPException(status_code=400, detail="No file received")
    
    if not file.filename:
        logger.error("No filename provided")
        raise HTTPException(status_code=400, detail="No filename provided")
    
    try:
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            logger.error(f"Invalid file type: {file.filename}")
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        # Check file size (optional - add reasonable limits)
        # if hasattr(file, 'size') and file.size > 50 * 1024 * 1024:  # 50MB limit
        #     logger.error(f"File too large: {file.size} bytes")
        #     raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as temp_file:
            content = await file.read()
            logger.info(f"Read {len(content)} bytes from uploaded file")
            
            if len(content) == 0:
                logger.error("Uploaded file is empty")
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"File uploaded successfully: {file.filename} -> {temp_file_path}")
        
        return {
            "filename": file.filename,
            "file_path": temp_file_path,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "message": "File uploaded successfully"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.post("/extract", response_model=ExtractionResponse)
async def extract_ontology(
    request: CSVUploadRequest,
    background_tasks: BackgroundTasks
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """
    Process CSV file and extract ontology.
    
    This endpoint starts an asynchronous ontology extraction process.
    Use the returned task_id to track progress via WebSocket or GET /extract/{task_id}.
    """
    logger.info(f"Extract endpoint called with request: {request.dict()}")
    
    try:
        # Validate that the file exists (moved from Pydantic validator to here)
        if not Path(request.file_path).exists():
            logger.error(f"File not found: {request.file_path}")
            raise HTTPException(status_code=400, detail=f"File not found: {request.file_path}")
        
        # Validate file extension
        if not request.file_path.lower().endswith('.csv'):
            logger.error(f"Invalid file type: {request.file_path}")
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Initialize task
        extraction_tasks[task_id] = {
            "status": "pending",
            "file_path": request.file_path,
            "config": request.extraction_config.dict() if request.extraction_config else {},
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "processing_time": None,
            "results": None,
            "error": None
        }
        
        logger.info(f"Created extraction task {task_id} for file {request.file_path}")
        
        # Start background task
        background_tasks.add_task(
            run_ontology_extraction,
            task_id,
            request.file_path,
            request.extraction_config
        )
        
        return ExtractionResponse(
            task_id=task_id,
            status="pending",
            message="Extraction task created and queued",
            created_at=extraction_tasks[task_id]["created_at"],
            estimated_completion=datetime.now() + timedelta(minutes=5)  # Rough estimate
        )
        
    except Exception as e:
        logger.error(f"Failed to create extraction task: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to create extraction task: {str(e)}")

@app.get("/extract/{task_id}", response_model=Dict[str, Any])
async def get_extraction_status(
    task_id: str
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """Get the status and results of an extraction task."""
    if task_id not in extraction_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # Ensure all data is properly serialized
        task_data = extraction_tasks[task_id]
        
        # Deep copy to avoid modifying original data
        import copy
        task_copy = copy.deepcopy(task_data)
        
        # Apply conversion recursively with safe serialization
        serialized_data = safe_serialize(task_copy)
        
        return serialized_data
    except Exception as e:
        logger.error(f"Error serializing task data: {str(e)}")
        logger.error(f"Task data keys: {list(task_data.keys()) if isinstance(task_data, dict) else 'Not a dict'}")
        
        # Return a simplified version if serialization fails
        return {
            "task_id": task_id,
            "status": task_data.get("status", "unknown"),
            "error": f"Serialization error: {str(e)}",
            "created_at": task_data.get("created_at"),
            "started_at": task_data.get("started_at"),
            "completed_at": task_data.get("completed_at"),
            "debug_info": {
                "task_keys": list(task_data.keys()) if isinstance(task_data, dict) else str(type(task_data)),
                "error_type": str(type(e)),
                "error_details": str(e)
            }
        }

@app.get("/entities", response_model=EntityResponse)
async def list_entities(
    task_id: Optional[str] = Query(None, description="Task ID to filter entities"),
    limit: int = Query(100, ge=1, le=1000, description="Number of entities to return"),
    offset: int = Query(0, ge=0, description="Number of entities to skip")
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """List extracted entities with pagination."""
    try:
        if task_id:
            if task_id not in extraction_tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            
            task = extraction_tasks[task_id]
            if task["status"] != "completed":
                raise HTTPException(status_code=400, detail="Task not completed")
            
            entities = task["results"]["entities"]
        else:
            # Return entities from all completed tasks
            entities = []
            for task in extraction_tasks.values():
                if task["status"] == "completed" and task["results"]:
                    entities.extend(task["results"]["entities"])
        
        # Apply pagination
        total_count = len(entities)
        paginated_entities = entities[offset:offset + limit]
        
        # Ensure all data is properly serialized
        serialized_entities = convert_numpy_types(paginated_entities)
        
        return EntityResponse(
            entities=serialized_entities,
            total_count=total_count,
            extraction_metadata={
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve entities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve entities: {str(e)}")

@app.get("/relationships", response_model=RelationshipResponse)
async def list_relationships(
    task_id: Optional[str] = Query(None, description="Task ID to filter relationships"),
    limit: int = Query(100, ge=1, le=1000, description="Number of relationships to return"),
    offset: int = Query(0, ge=0, description="Number of relationships to skip")
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """List discovered relationships with pagination."""
    try:
        if task_id:
            if task_id not in extraction_tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            
            task = extraction_tasks[task_id]
            if task["status"] != "completed":
                raise HTTPException(status_code=400, detail="Task not completed")
            
            relationships = task["results"]["relationships"]
        else:
            # Return relationships from all completed tasks
            relationships = []
            for task in extraction_tasks.values():
                if task["status"] == "completed" and task["results"]:
                    relationships.extend(task["results"]["relationships"])
        
        # Apply pagination
        total_count = len(relationships)
        paginated_relationships = relationships[offset:offset + limit]
        
        # Ensure all data is properly serialized
        serialized_relationships = convert_numpy_types(paginated_relationships)
        
        return RelationshipResponse(
            relationships=serialized_relationships,
            total_count=total_count,
            discovery_metadata={
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve relationships: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve relationships: {str(e)}")

@app.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """Submit user feedback for entities or relationships."""
    try:
        # In a real implementation, you would store this feedback
        # and use it to improve the extraction models
        
        feedback_id = str(uuid.uuid4())
        
        # Store feedback (simplified - in production, use proper database)
        feedback_data = {
            "id": feedback_id,
            "entity_id": request.entity_id,
            "relationship_id": request.relationship_id,
            "feedback_type": request.feedback_type,
            "feedback_value": request.feedback_value,
            "confidence_delta": request.confidence_delta,
            "user_id": request.user_id,
            "timestamp": datetime.now()
        }
        
        logger.info(f"Feedback received: {feedback_data}")
        
        return {
            "feedback_id": feedback_id,
            "status": "received",
            "message": "Feedback submitted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@app.get("/graph/visualize", response_model=GraphVisualizationResponse)
async def get_graph_visualization(
    task_id: str
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """Return Cypher queries for graph visualization."""
    try:
        if task_id not in extraction_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task = extraction_tasks[task_id]
        if task["status"] != "completed":
            raise HTTPException(status_code=400, detail="Task not completed")
        
        # Generate Cypher queries for visualization
        entities = task["results"]["entities"]
        relationships = task["results"]["relationships"]
        
        cypher_queries = []
        
        # Create nodes for entities
        for entity in entities:
            cypher_queries.append(
                f"CREATE (e:Entity {{id: '{entity['id']}', name: '{entity['name']}', "
                f"type: '{entity['entity_type']}', confidence: {entity['confidence']}}})"
            )
        
        # Create relationships
        for rel in relationships:
            cypher_queries.append(
                f"MATCH (a:Entity {{id: '{rel['source_entity_id']}'}}), "
                f"(b:Entity {{id: '{rel['target_entity_id']}'}}) "
                f"CREATE (a)-[r:{rel['relationship_type'].upper()}]->(b)"
            )
        
        return GraphVisualizationResponse(
            cypher_queries=cypher_queries,
            graph_metadata={
                "task_id": task_id,
                "entity_count": len(entities),
                "relationship_count": len(relationships)
            },
            node_count=len(entities),
            edge_count=len(relationships)
        )
        
    except Exception as e:
        logger.error(f"Failed to generate graph visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate graph visualization: {str(e)}")

@app.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics(
    # Temporarily disabled API key requirement for development
    # _: bool = Depends(verify_api_key)
):
    """Get system performance and extraction metrics."""
    try:
        # Calculate metrics
        total_tasks = len(extraction_tasks)
        completed_tasks = len([t for t in extraction_tasks.values() if t["status"] == "completed"])
        failed_tasks = len([t for t in extraction_tasks.values() if t["status"] == "failed"])
        
        # Calculate average processing time
        processing_times = [
            t["processing_time"] for t in extraction_tasks.values() 
            if t["processing_time"] is not None
        ]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return MetricsResponse(
            system_metrics={
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0
            },
            extraction_metrics={
                "average_processing_time": avg_processing_time,
                "total_entities_extracted": sum(
                    len(t["results"]["entities"]) 
                    for t in extraction_tasks.values() 
                    if t["status"] == "completed" and t["results"]
                ),
                "total_relationships_discovered": sum(
                    len(t["results"]["relationships"]) 
                    for t in extraction_tasks.values() 
                    if t["status"] == "completed" and t["results"]
                )
            },
            quality_metrics={
                "average_entity_confidence": 0.85,  # Placeholder - implement actual calculation
                "average_relationship_confidence": 0.78,  # Placeholder - implement actual calculation
                "data_coverage": 0.92  # Placeholder - implement actual calculation
            },
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Kubernetes deployment."""
    try:
        # Check dependencies
        dependencies = {
            "neo4j": "healthy",  # Placeholder - implement actual health checks
            "llm_server": "healthy",  # Placeholder - implement actual health checks
            "duckdb": "healthy"   # Placeholder - implement actual health checks
        }
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            version="1.0.0",
            dependencies=dependencies
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            version="1.0.0",
            dependencies={"error": str(e)}
        )

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes deployment."""
    try:
        # Check if the service is ready to handle requests
        config = await get_config()
        
        # Basic readiness checks
        if not config:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "Configuration not loaded"}
            )
        
        return {"status": "ready"}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(e)}
        )

@app.get("/health/public")
async def public_health_check():
    """Public health check endpoint (no authentication required)."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "message": "KnowledgeForge API is running"
    }

# WebSocket endpoint for real-time progress updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time extraction progress updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to KnowledgeForge extraction service",
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message (ping/pong for keep-alive)
                data = await websocket.receive_text()
                
                # Handle ping messages
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    global config
    
    try:
        logger.info("Starting KnowledgeForge Ontology Extraction API...")
        
        # Load configuration
        try:
            config = load_config()
            logger.info("Configuration loaded successfully")
        except Exception as config_error:
            logger.warning(f"Failed to load configuration: {str(config_error)}")
            logger.info("Using default configuration")
            # Create a minimal default config to prevent startup failure
            from ontology_extractor.config import OntologyExtractionConfig
            config = OntologyExtractionConfig()
        
        # Initialize components
        logger.info("Initializing ontology extraction components...")
        
        # Additional initialization can be added here
        
        logger.info("KnowledgeForge API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start API: {str(e)}")
        # Don't raise here to allow the server to start even with configuration issues
        logger.error("API will start with limited functionality")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down KnowledgeForge Ontology Extraction API...")
    
    # Close WebSocket connections
    for websocket in websocket_connections:
        try:
            await websocket.close()
        except Exception:
            pass
    
    # Clean up extraction tasks
    extraction_tasks.clear()
    
    logger.info("API shutdown complete")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "KnowledgeForge Ontology Extraction API",
        "version": "1.0.0",
        "description": "Semantic ontology extraction from CSV files with local LLM support",
        "endpoints": {
            "upload": "/upload",
            "extract": "/extract",
            "entities": "/entities",
            "relationships": "/relationships",
            "feedback": "/feedback",
            "graph_visualization": "/graph/visualize",
            "metrics": "/metrics",
            "health": "/health",
            "health_public": "/health/public",
            "ready": "/ready",
            "websocket": "/ws",
            "documentation": "/docs"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
