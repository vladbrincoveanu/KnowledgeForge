"""Code extraction endpoints for repository scanning."""

import json
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

from domain.models.code_entities import ExtractionResult, IncrementalScanResult
from infrastructure.graph.neo4j_manager import Neo4jGraphManager
from infrastructure.storage.metadata_store import MetadataStore
from infrastructure.llm.llm_manager import LLMManager
from services.code_extraction.c4_extractor import C4ArchitectureExtractor
from services.service_extraction.github_downloader import GitHubDownloader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["code-extraction"])

# In-memory storage for scan tasks (use Redis in production)
scan_tasks: dict[str, dict[str, Any]] = {}


def _save_c4_to_json(task_id: str, c4_architecture: dict) -> None:
    """Save C4 architecture to JSON file for easy debugging."""
    try:
        api_root = Path(__file__).resolve().parents[4]
        output_dir = api_root / "sources" / "data" / "c4_extractions"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{task_id}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(c4_architecture, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"Saved C4 architecture to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save C4 architecture to JSON: {e}", exc_info=True)


def _load_latest_c4_from_json() -> dict:
    """Load the most recent C4 architecture from JSON file."""
    try:
        api_root = Path(__file__).resolve().parents[4]
        output_dir = api_root / "sources" / "data" / "c4_extractions"

        if not output_dir.exists():
            logger.warning(f"C4 extractions directory does not exist: {output_dir}")
            return {}

        json_files = sorted(output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        if not json_files:
            logger.warning("No C4 extraction JSON files found")
            return {}

        latest_file = json_files[0]
        logger.info(f"Loading C4 architecture from {latest_file}")

        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load C4 architecture from JSON: {e}", exc_info=True)
        return {}


class ScanRequest(BaseModel):
    """Request model for repository scan."""
    repo_path: Optional[str] = Field(None, description="Local path to repository")
    use_c4_model: bool = Field(default=True, description="Use C4 Model (recommended) vs detailed extraction")
    max_components_per_domain: int = Field(default=10, description="Group components if more than this")

class GitHubScanRequest(BaseModel):
    """Request model for GitHub-based C4 scan."""
    github_url: str = Field(..., description="GitHub repository URL")
    use_git: bool = Field(default=True, description="Use git clone if available")
    max_components_per_domain: int = Field(default=10, description="Group components if more than this")
    append_mode: bool = Field(default=True, description="Append to existing data (True) or clear first (False)")


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
    containers_count: int = 0
    components_count: int = 0
    external_deps_count: int = 0
    errors: list[str] = Field(default_factory=list)
    extraction_mode: str = "c4_model"


def get_neo4j_manager():
    """Get Neo4j manager instance."""
    from utils.config import get_config
    config = get_config()
    manager = Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        encrypted=config.neo4j.encrypted,
        database=config.neo4j.database,
        max_connection_pool_size=config.neo4j.max_connection_pool_size,
        connection_timeout=config.neo4j.connection_timeout,
    )
    manager.connect()
    return manager


def get_llm_manager():
    """Get LLM manager instance."""
    try:
        import os
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = os.getenv("LMSTUDIO_MODEL_NAME", "qwen/qwen2.5-vl-7b")
        return LLMManager(lmstudio_url=base_url, default_model=model)
    except Exception as e:
        logger.warning(f"LLM not available: {e}")
        return None


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
        
        # Start background scan with C4 Model
        background_tasks.add_task(
            run_c4_extraction,
            task_id,
            repo_path,
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


@router.post("/extract-from-github", response_model=ScanResponse)
async def extract_from_github(
    request: GitHubScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Download a GitHub repository and run C4 extraction.
    """
    if not request.github_url:
        raise HTTPException(status_code=400, detail="github_url is required")

    if not GitHubDownloader.is_github_url(request.github_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    task_id = str(uuid.uuid4())
    scan_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0.0,
        'message': 'Repository download queued',
        'created_at': datetime.now(),
        'github_url': request.github_url,
        'errors': [],
    }

    try:
        temp_dir = Path(tempfile.mkdtemp(prefix=f"code_arch_{task_id}_"))
        repo_path = GitHubDownloader.download_repository(
            request.github_url,
            output_dir=temp_dir,
            use_git=request.use_git,
        )

        scan_tasks[task_id].update({
            'repo_path': str(repo_path),
            'temp_dir': str(temp_dir),
            'message': 'Repository downloaded, scan queued',
        })

        background_tasks.add_task(
            run_c4_extraction,
            task_id,
            repo_path,
            max_components=request.max_components_per_domain,
            append_mode=request.append_mode,
        )

        return ScanResponse(
            task_id=task_id,
            status='pending',
            message='Repository downloaded and scan queued',
            created_at=datetime.now(),
        )

    except Exception as e:
        logger.error(f"Failed to download repository: {e}")
        scan_tasks[task_id]['status'] = 'failed'
        scan_tasks[task_id]['message'] = f'Failed to download repository: {str(e)}'
        scan_tasks[task_id].setdefault('errors', []).append(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to download repository: {str(e)}")


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
    
    # Start background scan with C4 Model
    background_tasks.add_task(
        run_c4_extraction,
        task_id,
        repo_path,
        max_components=request.max_components_per_domain,
    )
    
    return ScanResponse(
        task_id=task_id,
        status='pending',
        message='Repository scan queued',
        created_at=datetime.now(),
    )


async def run_c4_extraction(
    task_id: str,
    repo_path: Path,
    max_components: int = 10,
    append_mode: bool = True,
):
    """Run C4 Model architecture extraction in background."""
    task = scan_tasks.get(task_id)
    if not task:
        logger.error(f"Task {task_id} not found in scan_tasks")
        return
    
    try:
        task['status'] = 'scanning'
        task['progress'] = 0.1
        task['message'] = 'Initializing C4 extractor'
        
        # Initialize LLM (optional)
        llm = get_llm_manager()
        
        # Initialize C4 extractor
        extractor = C4ArchitectureExtractor(repo_path=repo_path, llm_manager=llm)
        
        task['progress'] = 0.3
        task['message'] = 'Extracting C4 architecture'
        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")
        
        # Extract C4 architecture
        c4_architecture = extractor.extract(max_components_per_domain=max_components)
        
        task['progress'] = 0.7
        task['message'] = f'Extracted {len(c4_architecture["containers"])} containers, {len(c4_architecture["components"])} components'
        task['containers_count'] = len(c4_architecture['containers'])
        task['components_count'] = len(c4_architecture['components'])
        task['external_deps_count'] = len(c4_architecture['system_context'].get('external_dependencies', []))
        task['c4_architecture'] = c4_architecture

        # Save to JSON file for easy debugging
        _save_c4_to_json(task_id, c4_architecture)

        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")

        # Store in Neo4j (simplified for C4 model)
        task['progress'] = 0.8
        task['message'] = 'Storing architecture in graph database'
        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")
        
        await store_c4_in_neo4j(task_id, c4_architecture, append_mode=append_mode)
        
        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'C4 extraction completed successfully'
        task['completed_at'] = datetime.now()
        
        logger.info(f"C4 extraction completed for task {task_id}")
        
        # Cleanup temp directory if exists
        if 'temp_dir' in task:
            try:
                shutil.rmtree(task['temp_dir'])
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
    
    except Exception as e:
        logger.error(f"C4 extraction failed for task {task_id}: {e}", exc_info=True)
        
        task = scan_tasks.get(task_id)
        if task:
            task['status'] = 'failed'
            task['message'] = f'Extraction failed: {str(e)}'
            task.setdefault('errors', []).append(str(e))
            logger.error(f"Task {task_id} failed: {task['message']}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")


async def store_c4_in_neo4j(
    task_id: str,
    c4_architecture: dict[str, Any],
    append_mode: bool = True,
):
    """Store C4 architecture in Neo4j (simplified, clean structure).
    
    Args:
        task_id: Task identifier
        c4_architecture: C4 architecture data
        append_mode: If True, append to existing data. If False, clear first.
    """
    try:
        neo4j_manager = get_neo4j_manager()
        
        if not neo4j_manager.is_connected():
            neo4j_manager.connect()
        
        # Clear existing data if not in append mode
        if not append_mode:
            logger.info("Clearing existing C4 architecture data from Neo4j")
            neo4j_manager.execute_query(
                """
                MATCH (n)
                WHERE n:System OR n:Container OR n:Component OR n:ExternalService
                DETACH DELETE n
                """
            )
        
        # Store system context (Level 1)
        system = c4_architecture['system_context']
        system_ctx = system  # alias for clarity
        neo4j_manager.execute_query(
            """
            MERGE (s:System {name: $name})
            SET s.purpose = $purpose,
                s.c4_level = $c4_level,
                s.domain = $domain,
                s.owner = $owner,
                s.status = $status,
                s.tier = $tier,
                s.data_class = $data_class,
                s.active_experts = $active_experts,
                s.compliance = $compliance,
                s.updated_at = datetime()
            """,
            name=system['name'],
            purpose=system['purpose'],
            c4_level=system['c4_level'],
            domain=system_ctx.get('business_domain', system_ctx.get('domain', 'Unclassified')),
            owner=system_ctx.get('owner_team', system_ctx.get('owner', 'Unassigned')),
            status=system_ctx.get('status', 'Unknown'),
            tier=system_ctx.get('criticality', system_ctx.get('tier', 'Unknown')),
            data_class=system_ctx.get('data_class', 'Unknown'),
            active_experts=system_ctx.get('active_experts', 0),
            compliance=system_ctx.get('compliance', 'UNKNOWN'),
        )
        
        # Store external dependencies
        for dep in system.get('external_dependencies', []):
            neo4j_manager.execute_query(
                """
                MERGE (e:ExternalService {name: $name})
                SET e.type = $type,
                    e.url = $url
                WITH e
                MATCH (s:System {name: $system_name})
                MERGE (s)-[r:DEPENDS_ON]->(e)
                SET r.detected_from = $detected_from
                """,
                name=dep['name'],
                type=dep['type'],
                url=dep.get('url', ''),
                system_name=system['name'],
                detected_from=dep.get('detected_from', '')
            )
        
        # Store containers (Level 2) - inherit system-level fields for each container
        for container in c4_architecture['containers']:
            neo4j_manager.execute_query(
                """
                MERGE (c:Container {name: $name})
                SET c.container_type = $container_type,
                    c.technology = $technology,
                    c.protocol = $protocol,
                    c.c4_level = $c4_level,
                    c.path = $path,
                    c.owner = $owner,
                    c.domain = $domain,
                    c.status = $status,
                    c.tier = $tier,
                    c.data_class = $data_class,
                    c.active_experts = $active_experts,
                    c.compliance = $compliance
                WITH c
                MATCH (s:System {name: $system_name})
                MERGE (s)-[:CONTAINS]->(c)
                """,
                name=container['name'],
                container_type=container['container_type'],
                technology=container['technology'],
                protocol=container['protocol'],
                c4_level=container['c4_level'],
                path=container['path'],
                # Inherit from system context
                owner=system_ctx.get('owner_team', system_ctx.get('owner', 'Unassigned')),
                domain=system_ctx.get('business_domain', system_ctx.get('domain', 'Unclassified')),
                status=system_ctx.get('status', 'Unknown'),
                tier=system_ctx.get('criticality', system_ctx.get('tier', 'Unknown')),
                data_class=system_ctx.get('data_class', 'Unknown'),
                active_experts=system_ctx.get('active_experts', 0),
                compliance=system_ctx.get('compliance', 'UNKNOWN'),
                system_name=system['name']
            )
        
        # Store components (Level 3) - inherit system-level fields
        for component in c4_architecture['components']:
            neo4j_manager.execute_query(
                """
                MERGE (comp:Component {name: $name})
                SET comp.component_type = $component_type,
                    comp.c4_level = $c4_level,
                    comp.endpoint_path = $endpoint_path,
                    comp.endpoint_method = $endpoint_method,
                    comp.function_name = $function_name,
                    comp.file = $file,
                    comp.owner = $owner,
                    comp.domain = $domain,
                    comp.status = $status,
                    comp.tier = $tier,
                    comp.data_class = $data_class,
                    comp.active_experts = $active_experts,
                    comp.compliance = $compliance
                WITH comp
                MATCH (c:Container {name: $container_name})
                MERGE (c)-[:EXPOSES]->(comp)
                """,
                name=component['name'],
                component_type=component['component_type'],
                c4_level=component['c4_level'],
                endpoint_path=component.get('endpoint_path', ''),
                endpoint_method=component.get('endpoint_method', ''),
                function_name=component.get('function_name', ''),
                file=component.get('file', ''),
                container_name=component['container'],
                # Inherit from system context
                owner=system_ctx.get('owner_team', system_ctx.get('owner', 'Unassigned')),
                domain=system_ctx.get('business_domain', system_ctx.get('domain', 'Unclassified')),
                status=system_ctx.get('status', 'Unknown'),
                tier=system_ctx.get('criticality', system_ctx.get('tier', 'Unknown')),
                data_class=system_ctx.get('data_class', 'Unknown'),
                active_experts=system_ctx.get('active_experts', 0),
                compliance=system_ctx.get('compliance', 'UNKNOWN'),
            )
        
        logger.info(
            f"Stored C4 architecture: {len(c4_architecture['containers'])} containers, "
            f"{len(c4_architecture['components'])} components in Neo4j"
        )
    
    except Exception as e:
        logger.error(f"Failed to store C4 architecture in Neo4j: {e}", exc_info=True)
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
        containers_count=task.get('containers_count', 0),
        components_count=task.get('components_count', 0),
        external_deps_count=task.get('external_deps_count', 0),
        errors=task.get('errors', []),
    )


@router.get("/scan/{task_id}/results", response_model=dict[str, Any])
async def get_scan_results(task_id: str):
    """Get C4 architecture results of a completed scan."""
    task = scan_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Task not yet completed")
    
    c4_architecture: Optional[dict[str, Any]] = task.get('c4_architecture')
    if not c4_architecture:
        raise HTTPException(status_code=404, detail="Results not found")
    
    return {
        'task_id': task_id,
        'extraction_mode': 'c4_model',
        'system_context': c4_architecture['system_context'],
        'containers': c4_architecture['containers'],
        'components': c4_architecture['components'],
        'relationships': c4_architecture.get('relationships', {}),
        'statistics': {
            'total_containers': len(c4_architecture['containers']),
            'total_components': len(c4_architecture['components']),
            'total_external_deps': len(c4_architecture['system_context'].get('external_dependencies', [])),
        },
        'metadata': c4_architecture.get('metadata', {}),
        'errors': task.get('errors', []),
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


@router.post("/clear")
async def clear_architecture():
    """Clear all architecture data from Neo4j."""
    try:
        neo4j_manager = get_neo4j_manager()
        
        if not neo4j_manager.is_connected():
            neo4j_manager.connect()
        
        # Clear all nodes and relationships
        result = neo4j_manager.execute_query(
            """
            MATCH (n)
            WHERE n:System OR n:Container OR n:Component OR n:ExternalService
            WITH n
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
        )
        
        deleted_count = result[0]['deleted_count'] if result else 0
        logger.info(f"Cleared {deleted_count} nodes from Neo4j")
        
        return {
            "status": "success",
            "message": f"Cleared {deleted_count} nodes from database",
            "deleted_count": deleted_count
        }
    
    except Exception as e:
        logger.error(f"Failed to clear architecture: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear architecture: {str(e)}")


@router.get("/architecture")
async def get_code_architecture():
    """
    Get the C4 architecture data from JSON file.

    Returns the most recently extracted C4 architecture.
    This replaces Neo4j querying with simple JSON file reading for easier debugging.
    """
    try:
        # Load from JSON file
        c4_data = _load_latest_c4_from_json()

        if not c4_data:
            # Return empty structure if no data
            return {
                "c4_model_version": "1.0",
                "system_context": {
                    "name": "No Architecture Data",
                    "purpose": "No repository has been extracted yet",
                    "c4_level": "L1:Context",
                    "business_domain": "Unknown",
                    "owner_team": "Unassigned",
                    "criticality": "Unknown",
                    "languages": [],
                    "frameworks": [],
                    "external_dependencies": [],
                },
                "containers": [],
                "components": [],
                "relationships": {},
                "metadata": {
                    "extraction_mode": "json_file",
                    "total_systems": 0,
                },
            }

        # Return the loaded data directly
        return c4_data

    except Exception as e:
        logger.error(f"Failed to get architecture from JSON: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get architecture: {str(e)}"
        )
