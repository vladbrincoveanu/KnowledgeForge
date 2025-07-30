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
from ..Infrastructure.mongodb_connector import MongoDBConnector
from ..Infrastructure.config_manager import config_manager
from ..Domain.dtos import (
    ProcessFileRequest, ProcessDirectoryRequest, QueryRequest,
    ProcessingResponse, QueryResponse, StatusResponse
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
        sheet_name: Optional sheet name for XLSX files
        
    Returns:
        ProcessingResponse: Processing result
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only CSV and XLSX files are supported."
            )
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        
        try:
            # Process the file
            request = ProcessFileRequest(
                file_path=temp_file_path,
                collection_name=collection_name,
                sheet_name=sheet_name
            )
            
            response = data_processing_service.process_file(request)
            
            if not response.success:
                raise HTTPException(status_code=400, detail=response.error)
            
            return response
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/process/directory")
async def process_directory(
    directory_path: str = Form(...),
    file_pattern: str = Form("*")
) -> ProcessingResponse:
    """
    Process all files in a directory matching the pattern.
    
    Args:
        directory_path: Path to the directory
        file_pattern: File pattern to match (default: "*")
        
    Returns:
        ProcessingResponse: Processing result
    """
    try:
        if not os.path.exists(directory_path):
            raise HTTPException(status_code=400, detail="Directory does not exist")
        
        request = ProcessDirectoryRequest(
            directory_path=directory_path,
            file_pattern=file_pattern
        )
        
        response = data_processing_service.process_directory(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/status")
async def get_status() -> StatusResponse:
    """
    Get the status of all processed collections.
    
    Returns:
        StatusResponse: Status information
    """
    try:
        return data_processing_service.get_processing_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/collections")
async def list_collections() -> List[Dict[str, Any]]:
    """
    List all collections with their information.
    
    Returns:
        List[Dict[str, Any]]: List of collection information
    """
    try:
        return query_service.list_collections()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """
    Get information about a specific collection.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        Dict[str, Any]: Collection information
    """
    try:
        info = query_service.get_collection_info(collection_name)
        if "error" in info:
            raise HTTPException(status_code=404, detail=info["error"])
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        collection_name: Name of the collection
        query: MongoDB query as JSON string (optional)
        limit: Maximum number of documents to return
        skip: Number of documents to skip
        
    Returns:
        QueryResponse: Query results
    """
    try:
        # Parse query if provided
        parsed_query = None
        if query:
            import json
            try:
                parsed_query = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON query")
        
        request = QueryRequest(
            collection_name=collection_name,
            query=parsed_query,
            limit=limit,
            skip=skip
        )
        
        response = data_processing_service.query_data(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str) -> Dict[str, Any]:
    """
    Delete a collection and its metadata.
    
    Args:
        collection_name: Name of the collection to delete
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    try:
        success = query_service.delete_collection(collection_name)
        if success:
            return {"message": f"Collection '{collection_name}' deleted successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to delete collection '{collection_name}'")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/metadata/{collection_name}")
async def get_metadata(collection_name: str) -> Dict[str, Any]:
    """
    Get metadata for a specific collection.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        Dict[str, Any]: Collection metadata
    """
    try:
        info = query_service.get_collection_info(collection_name)
        if "error" in info:
            raise HTTPException(status_code=404, detail=info["error"])
        
        metadata = info.get("metadata", {})
        return {
            "collection_name": collection_name,
            "metadata": metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 