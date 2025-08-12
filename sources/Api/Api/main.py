"""
Main FastAPI Application

REST API endpoints for data processing and querying operations.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import uvicorn
import os
import tempfile
import shutil

from ..Application.services import DataProcessingService, QueryService
from ..Application.services.connection_detection_service import ConnectionDetectionService
from ..Infrastructure.mongodb_connector import MongoDBConnector
from ..Infrastructure.config_manager import config_manager
from ..Infrastructure.llm_analyzer import LLMAnalyzer
from ..Domain.dtos import (
    ProcessFileRequest, ProcessDirectoryRequest, QueryRequest,
    ProcessingResponse, QueryResponse, StatusResponse
)
from ..Domain.models import (
    ConnectionDetectionRequest, ConnectionDetectionResponse,
    EdgeConfirmationRequest, EdgeConfirmationResponse
)

# Load API configuration
api_config = config_manager.get_api_config()

# Initialize FastAPI app
app = FastAPI(
    title="Knowlly Data Processing API",
    description="API for processing CSV and XLSX files and storing data in MongoDB",
    version="1.0.0",
    debug=api_config['debug']
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
mongodb_connector = MongoDBConnector()
data_processing_service = DataProcessingService(mongodb_connector)
query_service = QueryService(mongodb_connector)

# Initialize LLM analyzer and connection detection service
llm_analyzer = LLMAnalyzer(use_local_llm=True)
connection_detection_service = ConnectionDetectionService(mongodb_connector, llm_analyzer)


@app.on_event("startup")
async def startup_event():
    """Initialize MongoDB connection on startup."""
    print("Starting up API...")
    try:
        if mongodb_connector.connect():
            print("✅ MongoDB connected successfully")
        else:
            print("⚠️  MongoDB connection failed, but API will continue")
    except Exception as e:
        print(f"⚠️  MongoDB connection error: {e}, but API will continue")


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection on shutdown."""
    mongodb_connector.disconnect()


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Knowlly Data Processing API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test MongoDB connection
        mongodb_connector.client.admin.command('ping')
        return {"status": "healthy", "mongodb": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "mongodb": "disconnected", "error": str(e)}


@app.post("/process/file")
async def process_file(
    file: UploadFile = File(...),
    collection_name: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None)
) -> ProcessingResponse:
    """
    Process a single file and store its data in MongoDB.
    
    Args:
        file: The file to process (CSV or XLSX)
        collection_name: Optional custom collection name
        sheet_name: Optional sheet name for Excel files
        
    Returns:
        ProcessingResponse with processing results
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="File must be CSV or Excel format"
            )
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        
        try:
            # Create request
            request = ProcessFileRequest(
                file_path=temp_file_path,
                collection_name=collection_name,
                sheet_name=sheet_name
            )
            
            # Process file
            response = data_processing_service.process_file(request)
            
            # If processing was successful, trigger connection detection
            if response.success and response.data:
                await _trigger_connection_detection(response.data.get('collection_name', ''))
            
            return response
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        return ProcessingResponse(
            success=False,
            message=f"Error processing file: {str(e)}",
            error=str(e)
        )


@app.post("/process/directory")
async def process_directory(
    directory_path: str = Form(...),
    file_pattern: str = Form("*")
) -> ProcessingResponse:
    """
    Process all files in a directory.
    
    Args:
        directory_path: Path to the directory
        file_pattern: File pattern to match
        
    Returns:
        ProcessingResponse with processing results
    """
    try:
        request = ProcessDirectoryRequest(
            directory_path=directory_path,
            file_pattern=file_pattern
        )
        
        response = data_processing_service.process_directory(request)
        
        # If processing was successful, trigger connection detection for new collections
        if response.success and response.data:
            new_collections = response.data.get('collections', [])
            for collection_info in new_collections:
                await _trigger_connection_detection(collection_info.get('name', ''))
        
        return response
        
    except Exception as e:
        return ProcessingResponse(
            success=False,
            message=f"Error processing directory: {str(e)}",
            error=str(e)
        )


@app.get("/status")
async def get_status() -> StatusResponse:
    """Get processing status and collection information."""
    try:
        return data_processing_service.get_processing_status()
    except Exception as e:
        return StatusResponse(
            success=False,
            total_collections=0,
            collections=[],
            error=str(e)
        )


@app.get("/collections")
async def list_collections() -> List[Dict[str, Any]]:
    """List all collections in the database."""
    try:
        collections = query_service.list_collections()
        return collections
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """Get information about a specific collection."""
    try:
        info = query_service.get_collection_info(collection_name)
        if info:
            # QueryService returns a plain dict already
            return info
        else:
            raise HTTPException(status_code=404, detail="Collection not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/{collection_name}")
async def query_data(
    collection_name: str,
    query: Optional[str] = Query(None, description="MongoDB query as JSON string"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of documents to return"),
    skip: int = Query(0, ge=0, description="Number of documents to skip")
) -> QueryResponse:
    """
    Query data from a collection.
    
    Args:
        collection_name: Name of the collection to query
        query: Optional MongoDB query as JSON string
        limit: Maximum number of documents to return
        skip: Number of documents to skip
        
    Returns:
        QueryResponse with query results
    """
    try:
        # Parse query string to dict
        query_dict = {}
        if query:
            import json
            query_dict = json.loads(query)
        
        request = QueryRequest(
            collection_name=collection_name,
            query=query_dict,
            limit=limit,
            skip=skip
        )
        
        return data_processing_service.query_data(request)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON query string")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str) -> Dict[str, Any]:
    """Delete a collection from the database."""
    try:
        success = query_service.delete_collection(collection_name)
        if success:
            return {"success": True, "message": f"Collection '{collection_name}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Collection not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metadata/{collection_name}")
async def get_metadata(collection_name: str) -> Dict[str, Any]:
    """Get metadata for a specific collection."""
    try:
        info = query_service.get_collection_info(collection_name)
        if info and info.metadata:
            return {
                "success": True,
                "metadata": info.metadata.dict()
            }
        else:
            raise HTTPException(status_code=404, detail="Collection or metadata not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# New endpoints for connection detection and edge management

@app.post("/connections/detect")
async def detect_connections(request: ConnectionDetectionRequest) -> ConnectionDetectionResponse:
    """
    Detect potential connections between a new collection and existing collections.
    
    Args:
        request: Connection detection request
        
    Returns:
        ConnectionDetectionResponse with potential connections
    """
    try:
        return connection_detection_service.detect_connections(request)
    except Exception as e:
        return ConnectionDetectionResponse(
            success=False,
            potential_connections=[],
            message="Failed to detect connections",
            error=str(e)
        )


@app.post("/connections/confirm")
async def confirm_connection(request: EdgeConfirmationRequest) -> EdgeConfirmationResponse:
    """
    Confirm a potential connection and create an edge.
    
    Args:
        request: Edge confirmation request
        
    Returns:
        EdgeConfirmationResponse with the created edge
    """
    try:
        return connection_detection_service.confirm_connection(request)
    except Exception as e:
        return EdgeConfirmationResponse(
            success=False,
            edge=None,
            message="Failed to confirm connection",
            error=str(e)
        )


@app.get("/connections/potential")
async def get_potential_connections(
    collection_name: Optional[str] = Query(None, description="Filter by collection name")
) -> List[Dict[str, Any]]:
    """
    Get potential connections, optionally filtered by collection.
    
    Args:
        collection_name: Optional collection name to filter by
        
    Returns:
        List of potential connections
    """
    try:
        connections = connection_detection_service.get_potential_connections(collection_name)
        return [connection.model_dump() for connection in connections]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connections/edges")
async def get_edges(
    collection_name: Optional[str] = Query(None, description="Filter by collection name")
) -> List[Dict[str, Any]]:
    """
    Get confirmed edges, optionally filtered by collection.
    
    Args:
        collection_name: Optional collection name to filter by
        
    Returns:
        List of edges
    """
    try:
        edges = connection_detection_service.get_edges(collection_name)
        return [edge.model_dump() for edge in edges]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connections/graph-data")
async def get_graph_data() -> Dict[str, Any]:
    """
    Get complete graph data including nodes and edges for the UI.
    
    Returns:
        Graph data with nodes and edges
    """
    try:
        # Get all collections as nodes
        collections = query_service.list_collections()
        nodes = []
        
        for collection in collections:
            # Skip system collections like "edges"
            if collection["collection_name"] in ["edges", "potential_connections"]:
                continue
                
            # Get detailed collection info including metadata
            collection_info = query_service.get_collection_info(collection["collection_name"])
            
            # Extract column names from metadata
            column_names = []
            if collection_info and collection_info.get("metadata") and hasattr(collection_info["metadata"], "columns"):
                column_names = list(collection_info["metadata"].columns.keys())
            
            node = {
                "id": collection["collection_name"],
                "label": collection["collection_name"],
                "type": "file",
                "metadata": {
                    "columns": len(column_names),
                    "fileSize": "Unknown",
                    "uploadDate": collection["created_at"]
                },
                "headers": column_names,  # Add actual column names
                "columns": collection_info["metadata"].columns if collection_info and collection_info.get("metadata") else {}
            }
            nodes.append(node)
        
        # Get all edges
        edges = connection_detection_service.get_edges()
        links = []
        
        for edge in edges:
            link = {
                "id": edge.id,
                "source": edge.source_collection,
                "target": edge.target_collection,
                "label": f"{edge.source_column} ↔ {edge.target_column}",
                "columnA": edge.source_column,
                "columnB": edge.target_column,
                "confidence": edge.confidence_score,
                "mergedMetadata": edge.merged_metadata.model_dump() if edge.merged_metadata else None,
                "llm_analysis": edge.llm_analysis.model_dump() if edge.llm_analysis else None,
                "type": edge.connection_type.value,
                "status": edge.status,
                "createdAt": edge.created_at.isoformat()
            }
            links.append(link)
        
        return {
            "nodes": nodes,
            "links": links
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-all-data")
async def clear_all_data() -> Dict[str, Any]:
    """
    Clear all data from MongoDB collections and any cached/temporary data.
    
    Returns:
        Dictionary with success status and message
    """
    try:
        cleared_items = []
        
        # Clear all collections from MongoDB
        db = mongodb_connector.db
        
        # Drop all collections except system collections
        collections_to_drop = []
        for collection_name in db.list_collection_names():
            if not collection_name.startswith('system.'):
                collections_to_drop.append(collection_name)
        
        # Drop each collection
        for collection_name in collections_to_drop:
            db.drop_collection(collection_name)
            cleared_items.append(f"collection:{collection_name}")
        
        # Clear any cached data in Redis (if available)
        try:
            import redis
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
            redis_client.flushdb()
            cleared_items.append("redis_cache")
        except Exception as redis_error:
            print(f"Warning: Could not clear Redis cache: {redis_error}")
        
        # Clear temporary files in the data directory
        try:
            import glob
            import os
            data_dir = "/app/data"
            if os.path.exists(data_dir):
                temp_files = glob.glob(os.path.join(data_dir, "*.tmp"))
                temp_files.extend(glob.glob(os.path.join(data_dir, "*.temp")))
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                        cleared_items.append(f"temp_file:{os.path.basename(temp_file)}")
                    except Exception as file_error:
                        print(f"Warning: Could not remove temp file {temp_file}: {file_error}")
        except Exception as file_error:
            print(f"Warning: Could not clear temp files: {file_error}")
        
        return {
            "success": True,
            "message": f"Cleared {len(collections_to_drop)} collections and all cached data from database",
            "collections_cleared": collections_to_drop,
            "cleared_items": cleared_items
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing data: {str(e)}",
            "collections_cleared": [],
            "cleared_items": []
        }


# Helper function to trigger connection detection
async def _trigger_connection_detection(new_collection_name: str):
    """Trigger connection detection for a newly added collection."""
    try:
        # Get existing collections
        collections = query_service.list_collections()
        existing_collections = [col["collection_name"] for col in collections if col["collection_name"] != new_collection_name]
        
        if existing_collections:
            # Create connection detection request
            request = ConnectionDetectionRequest(
                new_collection_name=new_collection_name,
                existing_collections=existing_collections
            )
            
            # Detect connections (this will be async in the future)
            response = connection_detection_service.detect_connections(request)
            
            if response.success:
                print(f"✅ Detected {len(response.potential_connections)} potential connections for {new_collection_name}")
            else:
                print(f"⚠️  Connection detection failed for {new_collection_name}: {response.error}")
                
    except Exception as e:
        print(f"⚠️  Error triggering connection detection: {str(e)}")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 