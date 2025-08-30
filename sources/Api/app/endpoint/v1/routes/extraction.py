"""Ontology extraction endpoints."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import tempfile

from pydantic import BaseModel, Field
from datetime import datetime

class ExtractionResponse(BaseModel):
    """Response model for extraction operations."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("/upload", response_model=Dict[str, Any])
async def upload_csv_file(file: UploadFile = File(...)):
    """
    Upload a CSV file for processing.
    
    This endpoint accepts CSV files and stores them temporarily for ontology extraction.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file received")
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    try:
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as temp_file:
            content = await file.read()
            
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        return {
            "filename": file.filename,
            "file_path": temp_file_path,
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "message": "File uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/", response_model=ExtractionResponse)
async def extract_ontology(
    file_path: str,
    background_tasks: BackgroundTasks,
    extraction_config: Optional[Dict[str, Any]] = None
):
    """
    Process CSV file and extract ontology.
    
    This endpoint starts an asynchronous ontology extraction process.
    Use the returned task_id to track progress via WebSocket or GET /extract/{task_id}.
    """
    try:
        # Validate that the file exists
        if not Path(file_path).exists():
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")
        
        # Validate file extension
        if not file_path.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # This would integrate with the actual extraction service
        # For now, return a mock response
        
        return ExtractionResponse(
            task_id=task_id,
            status="pending",
            message="Extraction task created and queued",
            created_at=datetime.now(),
            estimated_completion=datetime.now() + timedelta(minutes=5)
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to create extraction task: {str(e)}")


@router.get("/{task_id}", response_model=Dict[str, Any])
async def get_extraction_status(task_id: str):
    """Get the status and results of an extraction task."""
    # This would integrate with the actual task management system
    # For now, return a mock response
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task is being processed",
        "created_at": datetime.now().isoformat()
    }


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get the current status of a specific task."""
    # This would integrate with the actual task management system
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task is being processed",
        "created_at": datetime.now().isoformat()
    }
