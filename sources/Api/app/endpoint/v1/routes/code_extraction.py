"""Code extraction endpoints for repository scanning."""

import logging
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.domain.models.code_entities import ExtractionResult, IncrementalScanResult
from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.storage.metadata_store import (
    PostgreSQLMetadataStore as MetadataStore,
)
from app.services.code_extraction.repository_scanner import RepositoryScanner
from app.endpoint.v1.routes.websocket import broadcast_task_update
from utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["code-extraction"])

# In-memory storage for scan tasks (use Redis in production)
scan_tasks: dict[str, dict[str, Any]] = {}


class ScanRequest(BaseModel):
    """Request model for repository scan."""
    repo_path: Optional[str] = Field(None, description="Local path to repository")
    incremental: bool = Field(default=False, description="Perform incremental scan")
    force_full: bool = Field(default=False, description="Force full scan")
    ignore_patterns: list[str] = Field(default_factory=list, description="Additional patterns to ignore")


class ScanResponse(BaseModel):
    """Response model for scan operations."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")


class ScanStatusResponse(BaseModel):
    """Response model for scan status."""
    task_id: str
    status: str
    progress: float
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    entities_count: int = 0
    relationships_count: int = 0
    dependencies_count: int = 0
    errors: list[str] = Field(default_factory=list)
    incremental_summary: Optional[dict[str, int]] = None


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
    manager.connect()
    return manager


def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config=config)


@router.post("/upload-repo", response_model=ScanResponse)
async def upload_repository(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Upload a repository archive (zip) for scanning.
    
    This endpoint accepts a ZIP file containing a repository and
    extracts it for scanning.
    """
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    try:
        # Create task
        task_id = str(uuid.uuid4())
        
        # Save uploaded file
        temp_dir = Path(tempfile.mkdtemp(prefix=f"repo_{task_id}_"))
        zip_path = temp_dir / file.filename
        
        with open(zip_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Extract ZIP
        extract_dir = temp_dir / 'extracted'
        extract_dir.mkdir()
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find repository root (handle nested directories)
        repo_path = extract_dir
        subdirs = list(extract_dir.iterdir())
        if len(subdirs) == 1 and subdirs[0].is_dir():
            repo_path = subdirs[0]
        
        # Initialize task
        scan_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0.0,
            'message': 'Repository uploaded, scan queued',
            'created_at': datetime.now(),
            'repo_path': str(repo_path),
            'temp_dir': str(temp_dir),
            'errors': [],
        }
        
        # Start background scan
        background_tasks.add_task(
            run_repository_scan,
            task_id,
            repo_path,
            incremental=False,
            force_full=True,
        )
        
        return ScanResponse(
            task_id=task_id,
            status='pending',
            message='Repository uploaded and scan queued',
            created_at=datetime.now(),
        )
    
    except Exception as e:
        logger.error(f"Failed to upload repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload repository: {str(e)}")


@router.post("/scan", response_model=ScanResponse)
async def scan_repository(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Scan a repository (local path or previously uploaded).
    
    This endpoint starts an asynchronous repository scan.
    Use the returned task_id to track progress.
    """
    if not request.repo_path:
        raise HTTPException(status_code=400, detail="repo_path is required")
    
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository not found: {request.repo_path}")
    
    # Create task
    task_id = str(uuid.uuid4())
    
    scan_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0.0,
        'message': 'Scan queued',
        'created_at': datetime.now(),
        'repo_path': str(repo_path),
        'errors': [],
    }
    
    # Start background scan
    background_tasks.add_task(
        run_repository_scan,
        task_id,
        repo_path,
        incremental=request.incremental,
        force_full=request.force_full,
        ignore_patterns=request.ignore_patterns,
    )
    
    return ScanResponse(
        task_id=task_id,
        status='pending',
        message='Repository scan queued',
        created_at=datetime.now(),
    )


async def run_repository_scan(
    task_id: str,
    repo_path: Path,
    incremental: bool = False,
    force_full: bool = False,
    ignore_patterns: Optional[list[str]] = None,
):
    """Run repository scan in background."""
    task = scan_tasks.get(task_id)
    if not task:
        logger.error(f"Task {task_id} not found in scan_tasks")
        return
    
    try:
        task['status'] = 'scanning'
        task['progress'] = 0.1
        task['message'] = 'Initializing scanner'
        
        summary_payload = (
            {'incremental_summary': task['incremental_summary']}
            if task.get('incremental_summary')
            else None
        )
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
            extra=summary_payload,
        )
        
        # Initialize scanner
        scanner = RepositoryScanner(
            repo_path=repo_path,
            ignore_patterns=ignore_patterns or [],
        )
        
        task['progress'] = 0.2
        task['message'] = 'Scanning repository'
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # Perform scan
        scan_result: Optional[IncrementalScanResult] = None
        if incremental and not force_full:
            logger.info(f"Performing incremental scan for task {task_id}")
            scan_result = scanner.incremental_scan()
            # Incremental scan internally calls scan(), so last_result is set
            extraction_result = scanner.last_result
            if extraction_result is None:
                raise RuntimeError("Incremental scan did not produce an extraction result")
        else:
            logger.info(f"Performing full scan for task {task_id}")
            extraction_result = scanner.scan(force_full=force_full)
        
        task['progress'] = 0.6
        task['message'] = f'Extracted {len(extraction_result.entities)} entities'
        task['entities_count'] = len(extraction_result.entities)
        task['relationships_count'] = len(extraction_result.relationships)
        task['dependencies_count'] = len(extraction_result.dependencies)
        task['errors'] = extraction_result.errors
        task['extraction_result'] = extraction_result
        if scan_result:
            task['incremental_summary'] = {
                'added_entities': len(scan_result.added_entities),
                'modified_entities': len(scan_result.modified_entities),
                'deleted_entities': len(scan_result.deleted_entity_ids),
                'added_relationships': len(scan_result.added_relationships),
                'deleted_relationships': len(scan_result.deleted_relationship_ids),
            }
            task['incremental_result'] = scan_result
        
        summary_payload = (
            {'incremental_summary': task['incremental_summary']}
            if task.get('incremental_summary')
            else None
        )
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
            extra=summary_payload,
        )
        
        # Store in Neo4j
        task['progress'] = 0.7
        task['message'] = 'Storing in graph database'
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
            extra=summary_payload,
        )
        
        await store_code_entities_in_neo4j(task_id, extraction_result)
        
        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'Scan completed successfully'
        task['completed_at'] = datetime.now()
        
        await broadcast_task_update(
            task_id,
            'completed',
            message=task['message'],
            progress=100,
            extra=summary_payload,
        )
        
        logger.info(f"Repository scan completed for task {task_id}")
        
        # Cleanup temp directory if exists
        if 'temp_dir' in task:
            try:
                shutil.rmtree(task['temp_dir'])
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
    
    except Exception as e:
        logger.error(f"Repository scan failed for task {task_id}: {e}", exc_info=True)
        
        task = scan_tasks.get(task_id)
        if task:
            task['status'] = 'failed'
            task['message'] = f'Scan failed: {str(e)}'
            task.setdefault('errors', []).append(str(e))
            
            failure_payload = (
                {'incremental_summary': task['incremental_summary']}
                if task.get('incremental_summary')
                else None
            )
            try:
                await broadcast_task_update(
                    task_id,
                    'failed',
                    message=task['message'],
                    progress=0,
                    extra=failure_payload,
                )
            except Exception as broadcast_error:
                logger.error(f"Failed to broadcast task update: {broadcast_error}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")


async def store_code_entities_in_neo4j(
    task_id: str,
    extraction_result: ExtractionResult,
):
    """Store extracted code entities in Neo4j."""
    try:
        neo4j_manager = get_neo4j_manager()
        
        if not neo4j_manager.is_connected():
            neo4j_manager.connect()
        
        # Convert CodeEntity to Entity model format
        from app.domain.models.entities import Entity, Relationship
        
        # Store entities
        for code_entity in extraction_result.entities:
            if not code_entity.id:
                continue
            
            # Convert CodeEntity to Entity
            entity = Entity(
                id=code_entity.id,
                name=code_entity.name,
                entity_type=code_entity.entity_type.value,
                attributes={
                    'language': code_entity.language.value,
                    'source_type': code_entity.source_type.value,
                    'file_path': code_entity.file_path,
                    'line_start': code_entity.line_start,
                    'line_end': code_entity.line_end,
                    'signature': code_entity.signature,
                    'documentation': code_entity.documentation,
                    'modifiers': code_entity.modifiers,
                    **code_entity.attributes,
                },
                confidence=code_entity.confidence,
                source_columns=[],
            )
            
            neo4j_manager.store_entity_with_metadata(
                entity=entity,
                source_file=extraction_result.repository.repo_name or "repository",
                extraction_timestamp=datetime.now(),
                task_id=task_id,
            )
        
        # Store relationships
        for code_rel in extraction_result.relationships:
            if not code_rel.id:
                continue
            
            # Convert CodeRelationship to Relationship
            relationship = Relationship(
                id=code_rel.id,
                source_entity_id=code_rel.source_entity_id,
                target_entity_id=code_rel.target_entity_id,
                relationship_type=code_rel.relationship_type.value,
                attributes={
                    'direction': code_rel.direction,
                    'strength': code_rel.strength,
                    'context': code_rel.context,
                    'line_number': code_rel.line_number,
                    **code_rel.attributes,
                },
                confidence=code_rel.confidence,
                source_columns=[],
            )
            
            neo4j_manager.store_relationship_with_metadata(
                relationship=relationship,
                discovered_at=datetime.now(),
            )
        
        logger.info(
            f"Stored {len(extraction_result.entities)} entities and "
            f"{len(extraction_result.relationships)} relationships in Neo4j"
        )
    
    except Exception as e:
        logger.error(f"Failed to store in Neo4j: {e}", exc_info=True)
        raise


@router.get("/scan/{task_id}", response_model=ScanStatusResponse)
async def get_scan_status(task_id: str):
    """Get the status of a repository scan task."""
    task = scan_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return ScanStatusResponse(
        task_id=task_id,
        status=task['status'],
        progress=task['progress'],
        message=task['message'],
        created_at=task['created_at'],
        completed_at=task.get('completed_at'),
        entities_count=task.get('entities_count', 0),
        relationships_count=task.get('relationships_count', 0),
        dependencies_count=task.get('dependencies_count', 0),
        errors=task.get('errors', []),
        incremental_summary=task.get('incremental_summary'),
    )


@router.get("/scan/{task_id}/results", response_model=dict[str, Any])
async def get_scan_results(task_id: str):
    """Get detailed results of a completed scan."""
    task = scan_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Task not yet completed")
    
    extraction_result: Optional[ExtractionResult] = task.get('extraction_result')
    if not extraction_result:
        raise HTTPException(status_code=404, detail="Results not found")
    
    incremental_result = task.get('incremental_result')
    incremental_payload = (
        incremental_result.model_dump()
        if incremental_result and hasattr(incremental_result, "model_dump")
        else None
    )
    
    return {
        'task_id': task_id,
        'repository': extraction_result.repository.dict(),
        'statistics': {
            'total_files': len(extraction_result.files),
            'total_entities': len(extraction_result.entities),
            'total_relationships': len(extraction_result.relationships),
            'total_dependencies': len(extraction_result.dependencies),
            'languages_detected': [lang.value for lang in extraction_result.repository.languages_detected],
            'file_counts': extraction_result.repository.file_counts,
            'extraction_duration': extraction_result.extraction_duration_seconds,
        },
        'incremental_changes': incremental_payload,
        'entities': [e.dict() for e in extraction_result.entities[:100]],  # Limit for response size
        'relationships': [r.dict() for r in extraction_result.relationships[:100]],
        'dependencies': [d.dict() for d in extraction_result.dependencies[:100]],
        'errors': extraction_result.errors,
        'warnings': extraction_result.warnings,
    }


@router.delete("/scan/{task_id}")
async def delete_scan_task(task_id: str):
    """Delete a scan task and cleanup resources."""
    task = scan_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Cleanup temp directory if exists
    if 'temp_dir' in task:
        try:
            shutil.rmtree(task['temp_dir'])
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")
    
    del scan_tasks[task_id]
    
    return {"message": "Task deleted successfully"}


@router.get("/architecture")
async def get_code_architecture():
    """
    Get the C4 architecture data from the latest extraction.
    
    Serves the c4_architecture.json file from app-dev if it exists.
    """
    import json
    
    # Look for c4_architecture.json in the app-dev directory
    arch_file = Path(__file__).parent.parent.parent.parent.parent / "app-dev" / "c4_architecture.json"
    
    if not arch_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Architecture file not found. Please run extraction first: python -m services.code_extraction.c4_extractor"
        )
    
    try:
        with open(arch_file, 'r') as f:
            architecture_data = json.load(f)
        
        return architecture_data
    except Exception as e:
        logger.error(f"Failed to read architecture file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read architecture file: {str(e)}")

