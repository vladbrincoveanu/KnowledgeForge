"""Service extraction endpoints for GitHub and ZIP repositories."""

import logging
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.domain.models.services import ServiceGraph
from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.storage.metadata_store import (
    PostgreSQLMetadataStore as MetadataStore,
)
from app.infrastructure.llm.llm_manager import LLMManager
from app.services.service_extraction import (
    ServiceExtractionPipeline,
    ServiceRelationshipDiscoverer,
)
from app.services.service_extraction.github_downloader import GitHubDownloader
from app.services.service_extraction.extraction_config import (
    ExtractionConfig,
    JSONResultStore,
)
from app.endpoint.v1.routes.websocket import broadcast_task_update
from utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["service-extraction"])

# In-memory storage for extraction tasks (use Redis in production)
extraction_tasks: dict[str, dict[str, Any]] = {}


def _generate_task_id() -> str:
    """Human-readable task id with timestamp prefix for easier debugging."""
    now = datetime.now().strftime("%Y%m%d-%H%M")
    short = uuid.uuid4().hex[:6]
    return f"{now}-{short}"


def _build_llm_url(base_url: str, path: str) -> str:
    """Build LLM URL that works with or without /v1 in base_url."""
    base = base_url.rstrip("/")
    suffix = path.lstrip("/")
    if base.endswith("/v1"):
        return f"{base}/{suffix}"
    return f"{base}/v1/{suffix}"


def _probe_llm_models(base_url: str, headers: Optional[dict[str, str]] = None) -> bool:
    """Check if the LLM service responds to the models endpoint."""
    try:
        response = requests.get(
            _build_llm_url(base_url, "/models"),
            headers=headers,
            timeout=3,
        )
        if headers:
            return response.status_code == 200
        return response.status_code in {200, 401, 403}
    except Exception as exc:
        logger.warning(f"LLM probe failed for {base_url}: {exc}")
        return False


class ServiceExtractionRequest(BaseModel):
    """Request model for service extraction."""
    github_url: Optional[str] = Field(None, description="GitHub repository URL")
    repo_path: Optional[str] = Field(None, description="Local path to repository")
    use_git: bool = Field(default=True, description="Use git clone if available")


class ServiceExtractionResponse(BaseModel):
    """Response model for extraction operations."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Task creation timestamp")


class ServiceExtractionStatusResponse(BaseModel):
    """Response model for extraction status."""
    task_id: str
    status: str
    progress: float
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    services_count: int = 0
    connections_count: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

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


@router.post("/extract-from-github", response_model=ServiceExtractionResponse)
async def extract_from_github(
    request: ServiceExtractionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Extract services from a GitHub repository.
    
    This endpoint downloads a GitHub repository and extracts service information.
    """
    if not request.github_url:
        raise HTTPException(status_code=400, detail="github_url is required")
    
    if not GitHubDownloader.is_github_url(request.github_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    
    # Create task
    task_id = _generate_task_id()
    
    extraction_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0.0,
        'message': 'Service extraction queued',
        'created_at': datetime.now(),
        'github_url': request.github_url,
        'errors': [],
        'warnings': [],
    }
    
    try:
        # Start background extraction
        background_tasks.add_task(
            run_service_extraction,
            task_id,
            github_url=request.github_url,
            use_git=request.use_git,
        )
        
        return ServiceExtractionResponse(
            task_id=task_id,
            status='pending',
            message='Service extraction queued',
            created_at=datetime.now(),
        )
    except Exception as e:
        # Mark task as failed if background task creation fails
        if task_id in extraction_tasks:
            extraction_tasks[task_id]['status'] = 'failed'
            extraction_tasks[task_id]['message'] = f'Failed to start extraction: {str(e)}'
            extraction_tasks[task_id]['errors'].append(str(e))
        logger.error(f"Error in extract_from_github: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start extraction: {str(e)}")


@router.post("/extract-from-zip", response_model=ServiceExtractionResponse)
async def extract_from_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Extract services from a ZIP file containing a repository.
    
    This endpoint accepts a ZIP file and extracts service information.
    """
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    try:
        # Create task
        task_id = _generate_task_id()
        
        # Save uploaded file
        temp_dir = Path(tempfile.mkdtemp(prefix=f"service_extract_{task_id}_"))
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
        extraction_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0.0,
            'message': 'Repository uploaded, extraction queued',
            'created_at': datetime.now(),
            'repo_path': str(repo_path),
            'temp_dir': str(temp_dir),
            'errors': [],
            'warnings': [],
        }
        
        # Start background extraction
        background_tasks.add_task(
            run_service_extraction,
            task_id,
            repo_path=repo_path,
        )
        
        return ServiceExtractionResponse(
            task_id=task_id,
            status='pending',
            message='Repository uploaded and extraction queued',
            created_at=datetime.now(),
        )
    
    except Exception as e:
        logger.error(f"Failed to upload repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload repository: {str(e)}")


@router.post("/extract-from-path", response_model=ServiceExtractionResponse)
async def extract_from_path(
    request: ServiceExtractionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Extract services from a local repository path.
    
    This endpoint extracts service information from an existing local repository.
    """
    if not request.repo_path:
        raise HTTPException(status_code=400, detail="repo_path is required")
    
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository not found: {request.repo_path}")
    
    # Create task
    task_id = _generate_task_id()
    
    extraction_tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0.0,
        'message': 'Service extraction queued',
        'created_at': datetime.now(),
        'repo_path': str(repo_path),
        'errors': [],
        'warnings': [],
    }
    
    # Start background extraction
    background_tasks.add_task(
        run_service_extraction,
        task_id,
        repo_path=repo_path,
    )
    
    return ServiceExtractionResponse(
        task_id=task_id,
        status='pending',
        message='Service extraction queued',
        created_at=datetime.now(),
    )


def run_service_extraction(
    task_id: str,
    github_url: Optional[str] = None,
    repo_path: Optional[Path] = None,
    use_git: bool = True,
):
    """
    Run service extraction synchronously for BackgroundTasks.
    
    BackgroundTasks runs in a separate thread, so async functions with await
    won't work properly. This wrapper executes the extraction synchronously.
    """
    import asyncio
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_run_service_extraction_async(
            task_id=task_id,
            github_url=github_url,
            repo_path=repo_path,
            use_git=use_git,
        ))
    finally:
        loop.close()


async def _run_service_extraction_async(
    task_id: str,
    github_url: Optional[str] = None,
    repo_path: Optional[Path] = None,
    use_git: bool = True,
):
    """Run service extraction in background."""
    task = extraction_tasks.get(task_id)
    if not task:
        logger.error(f"Task {task_id} not found in extraction_tasks")
        return
    
    temp_dir: Optional[Path] = None
    
    try:
        task['status'] = 'extracting'
        task['progress'] = 0.1
        task['message'] = 'Downloading repository' if github_url else 'Initializing extraction'
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # Download from GitHub if needed
        if github_url:
            temp_dir = Path(tempfile.mkdtemp(prefix=f"service_extract_{task_id}_"))
            repo_path = GitHubDownloader.download_repository(
                github_url,
                output_dir=temp_dir,
                use_git=use_git,
                full_history=ExtractionConfig.GIT_CLONE_FOR_ANALYSIS,
            )
            task['repo_path'] = str(repo_path)
            task['temp_dir'] = str(temp_dir)
        
        if not repo_path:
            raise ValueError("No repository path available")
        
        repo_path = Path(repo_path)
        
        task['progress'] = 0.3
        task['message'] = 'Extracting services'
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # Extract services
        llm_manager = None
        enable_llm = getattr(ExtractionConfig, 'ENABLE_LLM_DESCRIPTIONS', False)
        enable_llm_labels = getattr(ExtractionConfig, 'ENABLE_LLM_LABELS', False)
        if enable_llm or enable_llm_labels:
            try:
                import os
                
                provider_pref = os.getenv("KF_LLM_PROVIDER", "lmstudio").strip().lower()
                # Check for OpenAI API key first
                openai_api_key = os.getenv('OPENAI_API_KEY', '').strip()
                openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
                openai_base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
                
                config = get_config()
                llm_cfg = config.lmstudio
                # Get base URL - if it doesn't end with /v1, add it for local LLM compatibility
                base_url_raw = os.getenv("LMSTUDIO_BASE_URL", llm_cfg.base_url)
                if base_url_raw.endswith("/v1"):
                    lmstudio_url = base_url_raw
                elif base_url_raw.endswith("/"):
                    lmstudio_url = base_url_raw.rstrip("/") + "/v1"
                else:
                    lmstudio_url = base_url_raw.rstrip("/") + "/v1"
                
                lmstudio_model = (
                    os.getenv("LMSTUDIO_MODEL")
                    or os.getenv("LMSTUDIO_MODEL_NAME")
                    or os.getenv("KF_LMSTUDIO_MODEL")
                    or llm_cfg.model_name
                )
                
                logger.info(f"LLM configuration: base_url={lmstudio_url}, model={lmstudio_model}")

                openai_ready = False
                if openai_api_key:
                    openai_headers = {"Authorization": f"Bearer {openai_api_key}"}
                    openai_ready = _probe_llm_models(openai_base_url, openai_headers)

                lmstudio_ready = _probe_llm_models(lmstudio_url)

                logger.info(
                    "LLM provider preference=%s, openai_ready=%s, lmstudio_ready=%s, lmstudio_url=%s, lmstudio_model=%s",
                    provider_pref,
                    openai_ready,
                    lmstudio_ready,
                    lmstudio_url,
                    lmstudio_model,
                )

                def use_openai():
                    logger.info(f"Using OpenAI API with model: {openai_model}")
                    return LLMManager(
                        default_model=openai_model,
                        use_embeddings=False,  # OpenAI doesn't need local embeddings
                        rate_limit_requests=100,  # Higher rate limit for OpenAI
                        rate_limit_window=60,
                        openai_api_key=openai_api_key,
                        openai_base_url=openai_base_url,
                    )

                def use_lmstudio():
                    logger.info(f"Using LM Studio at {lmstudio_url} (model: {lmstudio_model})")
                    manager = LLMManager(
                        lmstudio_url=lmstudio_url,
                        default_model=lmstudio_model,
                        use_embeddings=llm_cfg.use_embeddings,
                        rate_limit_requests=60,  # Local LM Studio rate limit
                        rate_limit_window=60,
                    )
                    manager.timeout = llm_cfg.timeout
                    return manager

                # Try to use LLM even if probe fails - the actual call might work
                if provider_pref in {"lmstudio", "local"}:
                    if lmstudio_ready:
                        llm_manager = use_lmstudio()
                    else:
                        logger.warning(f"LM Studio probe failed for {lmstudio_url}, but attempting to use it anyway (probe may be too strict)")
                        try:
                            llm_manager = use_lmstudio()
                        except Exception as e:
                            logger.warning(f"Failed to initialize LM Studio: {e}")
                            if openai_ready:
                                logger.warning("Falling back to OpenAI")
                                llm_manager = use_openai()
                            else:
                                llm_manager = None
                elif provider_pref == "openai":
                    if openai_ready:
                        llm_manager = use_openai()
                    elif lmstudio_ready:
                        logger.warning("OpenAI not reachable, falling back to LM Studio")
                        llm_manager = use_lmstudio()
                    else:
                        logger.warning("Neither OpenAI nor LM Studio are reachable")
                        llm_manager = None
                else:
                    # Default: try LM Studio first, then OpenAI
                    if lmstudio_ready:
                        llm_manager = use_lmstudio()
                    elif openai_ready:
                        llm_manager = use_openai()
                    else:
                        logger.warning(f"Both LLM providers failed probe, but attempting LM Studio anyway at {lmstudio_url}")
                        try:
                            llm_manager = use_lmstudio()
                        except Exception as e:
                            logger.warning(f"Failed to initialize LM Studio: {e}")
                            llm_manager = None
            except Exception as e:
                logger.warning(f"LLM manager initialization failed, using heuristic descriptions only: {e}")
                llm_manager = None
        
        logger.info(f"Creating ServiceExtractionPipeline for path: {repo_path}")
        pipeline = ServiceExtractionPipeline(repo_path, llm_manager=llm_manager)
        logger.info("Calling extract_services()...")
        services, context_nodes = pipeline.extract_services()
        logger.info(f"extract_services() completed, found {len(services)} services and {len(context_nodes)} context nodes")
        
        task['progress'] = 0.6
        task['message'] = f'Found {len(services)} services, discovering connections'
        task['services_count'] = len(services)
        task['errors'].extend(pipeline.errors)
        task['warnings'].extend(pipeline.warnings)
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # Discover relationships
        relationship_discoverer = ServiceRelationshipDiscoverer(repo_path, services)
        connections = relationship_discoverer.discover_connections()
        
        task['progress'] = 0.8
        task['message'] = f'Discovered {len(connections)} connections'
        task['connections_count'] = len(connections)
        task['errors'].extend(relationship_discoverer.errors)
        task['warnings'].extend(relationship_discoverer.warnings)
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # Create service graph
        service_graph = ServiceGraph(
            services=services,
            connections=connections,
            context_nodes=context_nodes,
            repository_url=github_url,
            repository_name=repo_path.name,
        )
        
        task['service_graph'] = service_graph
        task['progress'] = 0.9
        task['message'] = 'Storing results'
        
        await broadcast_task_update(
            task_id,
            task['status'],
            message=task['message'],
            progress=int(task['progress'] * 100),
        )
        
        # ═══════════════════════════════════════════════════════════════════════════
        # FEATURE FLAG: Choose storage backend
        # ═══════════════════════════════════════════════════════════════════════════
        
        # Store to JSON files (for easy debugging and AI access)
        if ExtractionConfig.STORE_TO_JSON:
            await store_service_graph_to_json(task_id, service_graph)
        
        # Store to Neo4j (optional, controlled by feature flag)
        if ExtractionConfig.STORE_TO_NEO4J:
            await store_service_graph_in_neo4j(task_id, service_graph)
        
        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'Service extraction completed successfully'
        task['completed_at'] = datetime.now()
        
        await broadcast_task_update(
            task_id,
            'completed',
            message=task['message'],
            progress=100,
        )
        
        logger.info(f"Service extraction completed for task {task_id}")
        
        # Cleanup temp directory if exists
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
        elif 'temp_dir' in task:
            try:
                shutil.rmtree(task['temp_dir'])
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
    
    except Exception as e:
        logger.error(f"Service extraction failed for task {task_id}: {e}", exc_info=True)
        
        task = extraction_tasks.get(task_id)
        if task:
            task['status'] = 'failed'
            task['message'] = f'Extraction failed: {str(e)}'
            task.setdefault('errors', []).append(str(e))
            
            try:
                await broadcast_task_update(
                    task_id,
                    'failed',
                    message=task['message'],
                    progress=0,
                )
            except Exception as broadcast_error:
                logger.error(f"Failed to broadcast task update: {broadcast_error}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")


async def store_service_graph_in_neo4j(
    task_id: str,
    service_graph: ServiceGraph,
):
    """Store service graph in Neo4j."""
    try:
        neo4j_manager = get_neo4j_manager()
        
        if not neo4j_manager.is_connected():
            neo4j_manager.connect()
        
        # Convert Service to Entity model format
        from app.domain.models.entities import Entity, Relationship
        
        # Store services as entities
        for service in service_graph.services:
            entity = Entity(
                id=service.id,
                name=service.name,
                entity_type='service',
                attributes={
                    # ═══════════════════════════════════════════════════════════
                    # THE 5 PRIMARY EXTRACTION FIELDS
                    # ═══════════════════════════════════════════════════════════
                    'domain': service.domain,                # 1. Business domain
                    'owner': service.owner,                  # 2. Squad/team owner
                    'status': service.status.value,          # 3. Lifecycle status
                    'tier': service.tier.value,              # 4. Criticality tier
                    'data_class': service.data_class,        # 5. Data sensitivity
                    # ═══════════════════════════════════════════════════════════
                    # Additional metadata (secondary)
                    'display_name': service.display_name,
                    'description': service.description,
                    'language': service.language,
                    'framework': service.framework,
                    'port': service.port,
                    'endpoints': service.endpoints,
                    'repository_url': service.repository_url,
                    'file_path': service.file_path,
                    **service.attributes,
                },
                confidence=service.confidence,
                source_columns=[],
            )
            
            neo4j_manager.store_entity_with_metadata(
                entity=entity,
                source_file=service_graph.repository_name or "service_extraction",
                extraction_timestamp=datetime.now(),
                task_id=task_id,
            )
        
        # Store connections as relationships
        for connection in service_graph.connections:
            relationship = Relationship(
                id=connection.id,
                source_entity_id=connection.source_service_id,
                target_entity_id=connection.target_service_id,
                relationship_type=connection.connection_type.value,
                attributes={
                    'protocol': connection.protocol,
                    'endpoint': connection.endpoint,
                    'method': connection.method,
                    'strength': connection.strength,
                    'frequency': connection.frequency,
                    'context': connection.context,
                    'file_path': connection.file_path,
                    'line_number': connection.line_number,
                    **connection.attributes,
                },
                confidence=connection.confidence,
                source_columns=[],
            )
            
            neo4j_manager.store_relationship_with_metadata(
                relationship=relationship,
                discovered_at=datetime.now(),
            )
        
        logger.info(
            f"Stored {len(service_graph.services)} services and "
            f"{len(service_graph.connections)} connections in Neo4j"
        )
    
    except Exception as e:
        logger.error(f"Failed to store in Neo4j: {e}", exc_info=True)
        raise


async def store_service_graph_to_json(
    task_id: str,
    service_graph: ServiceGraph,
):
    """
    Store service graph to JSON files for easy access and debugging.
    
    Output files:
    - data/extractions/{task_id}/metadata.json
    - data/extractions/{task_id}/services.json
    - data/extractions/{task_id}/connections.json
    - data/extractions/{task_id}/summary.json
    """
    try:
        json_store = JSONResultStore(task_id)
        
        # Save metadata
        json_store.save_metadata(
            status="completed",
            repository_url=service_graph.repository_url,
            repository_name=service_graph.repository_name,
            started_at=None,  # Will be set when available
            completed_at=datetime.now(),
        )
        
        # Convert services to dicts with the 5 primary fields + new enhancements
        services_data = []
        for service in service_graph.services:
            svc_dict = {
                # ═══════════════════════════════════════════════════════════
                # THE 5 PRIMARY EXTRACTION FIELDS
                # ═══════════════════════════════════════════════════════════
                "domain": service.domain,
                "owner": service.owner,
                "owner_contributors": service.owner_contributors,
                "owner_contributor_stats": service.owner_contributor_stats,
                "contributor_count": service.contributor_count,
                "status": service.status.value if hasattr(service.status, 'value') else str(service.status),
                "status_evidence": service.status_evidence,
                "tier": service.tier.value if hasattr(service.tier, 'value') else str(service.tier),
                "data_class": service.data_class,
                # ═══════════════════════════════════════════════════════════
                # Service identity
                "id": service.id,
                "name": service.name,
                "display_name": service.display_name,
                "description": service.description,
                "notes": service.notes or service.description,
                # ═══════════════════════════════════════════════════════════
                # Technical details
                "language": service.language,
                "framework": service.framework,
                "port": service.port,
                "file_path": service.file_path,
                "source": service.source,
                # ═══════════════════════════════════════════════════════════
                # Dependencies
                "direct_depends": service.direct_depends,
                "dependencies": service.dependencies,
                "dependents": service.dependents,
                # ═══════════════════════════════════════════════════════════
                # Git activity metrics
                "last_commit_date": service.last_commit_date.isoformat() if service.last_commit_date else None,
                "commit_count_30d": service.commit_count_30d,
                "commit_count_90d": service.commit_count_90d,
                "commit_count_180d": service.commit_count_180d,
                # ═══════════════════════════════════════════════════════════
                # Additional
                "attributes": service.attributes,
                "confidence": service.confidence,
            }
            services_data.append(svc_dict)
        
        json_store.save_services(services_data)
        
        # Convert connections to dicts
        connections_data = []
        for connection in service_graph.connections:
            conn_dict = {
                "id": connection.id,
                "source_service_id": connection.source_service_id,
                "target_service_id": connection.target_service_id,
                "connection_type": connection.connection_type.value if hasattr(connection.connection_type, 'value') else str(connection.connection_type),
                "protocol": connection.protocol,
                "endpoint": connection.endpoint,
                "strength": connection.strength,
                "file_path": connection.file_path,
                "confidence": connection.confidence,
            }
            connections_data.append(conn_dict)
        
        json_store.save_connections(connections_data)
        
        # Convert context nodes to dicts
        context_nodes_data = []
        for node in service_graph.context_nodes:
            node_dict = {
                "id": node.id,
                "name": node.name,
                "type": node.type.value if hasattr(node.type, 'value') else str(node.type),
                "file_path": node.file_path,
                "content_preview": node.content_preview,
                "service_id": node.service_id,
                "attributes": node.attributes,
                "extracted_at": node.extracted_at.isoformat() if node.extracted_at else None,
            }
            context_nodes_data.append(node_dict)
        
        json_store.save_context_nodes(context_nodes_data)
        
        # Save summary (human-readable)
        json_store.save_summary(
            services=services_data,
            connections=connections_data,
            context_nodes=context_nodes_data,
            repository_name=service_graph.repository_name,
        )
        
        logger.info(
            f"Stored {len(services_data)} services and "
            f"{len(connections_data)} connections to JSON files at {json_store.get_output_path()}"
        )
    
    except Exception as e:
        logger.error(f"Failed to store to JSON: {e}", exc_info=True)
        # Don't raise - JSON storage failure shouldn't break the extraction
        logger.warning("JSON storage failed but extraction continues")


@router.get("/extraction/{task_id}", response_model=ServiceExtractionStatusResponse)
async def get_extraction_status(task_id: str):
    """Get the status of a service extraction task."""
    task = extraction_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return ServiceExtractionStatusResponse(
        task_id=task_id,
        status=task['status'],
        progress=task['progress'],
        message=task['message'],
        created_at=task['created_at'],
        completed_at=task.get('completed_at'),
        services_count=task.get('services_count', 0),
        connections_count=task.get('connections_count', 0),
        errors=task.get('errors', []),
        warnings=task.get('warnings', []),
    )


@router.get("/extraction/{task_id}/results", response_model=dict[str, Any])
async def get_extraction_results(task_id: str):
    """
    Get detailed results of a completed extraction.
    
    If JSON storage is enabled, loads from JSON files.
    Otherwise, loads from in-memory task storage.
    """
    task = extraction_tasks.get(task_id)
    
    # Try to load from JSON first (if available)
    if ExtractionConfig.STORE_TO_JSON:
        json_store = JSONResultStore(task_id)
        summary = json_store.load_summary()
        
        if summary:
            services = json_store.load_services()
            connections = json_store.load_connections()
            
            # Get file paths with download URLs
            output_path = json_store.get_output_path()
            json_files = {
                'metadata': {
                    'container_path': str(output_path / 'metadata.json'),
                    'host_path': f'sources/data/extractions/{task_id}/metadata.json',
                    'download_url': f'/api/v1/services/extraction/{task_id}/json/metadata',
                },
                'services': {
                    'container_path': str(output_path / 'services.json'),
                    'host_path': f'sources/data/extractions/{task_id}/services.json',
                    'download_url': f'/api/v1/services/extraction/{task_id}/json/services',
                },
                'connections': {
                    'container_path': str(output_path / 'connections.json'),
                    'host_path': f'sources/data/extractions/{task_id}/connections.json',
                    'download_url': f'/api/v1/services/extraction/{task_id}/json/connections',
                },
                'summary': {
                    'container_path': str(output_path / 'summary.json'),
                    'host_path': f'sources/data/extractions/{task_id}/summary.json',
                    'download_url': f'/api/v1/services/extraction/{task_id}/json/summary',
                },
            }
            
            return {
                'task_id': task_id,
                'repository': {
                    'name': summary.get('repository'),
                },
                'statistics': summary.get('statistics', {}),
                'services': services,
                'connections': connections,
                'errors': [],
                'warnings': [],
                'json_files': json_files,
                'json_output_path': str(output_path),
            }
    
    # Fall back to in-memory task storage
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Task not yet completed")
    
    service_graph: Optional[ServiceGraph] = task.get('service_graph')
    if not service_graph:
        raise HTTPException(status_code=404, detail="Results not found")
    
    return {
        'task_id': task_id,
        'repository': {
            'url': service_graph.repository_url,
            'name': service_graph.repository_name,
        },
        'statistics': {
            'total_services': service_graph.total_services,
            'total_connections': service_graph.total_connections,
        },
        'services': [s.model_dump() for s in service_graph.services],
        'connections': [c.model_dump() for c in service_graph.connections],
        'errors': task.get('errors', []),
        'warnings': task.get('warnings', []),
    }


@router.get("/extraction/{task_id}/json/{file_type}")
async def download_json_file(task_id: str, file_type: str):
    """
    Download a specific JSON file from extraction results.
    
    Args:
        task_id: Extraction task ID
        file_type: Type of file to download (metadata, services, connections, summary)
    
    Returns:
        JSON file as download
    """
    if file_type not in ['metadata', 'services', 'connections', 'summary']:
        raise HTTPException(status_code=400, detail="Invalid file type. Must be: metadata, services, connections, or summary")
    
    json_store = JSONResultStore(task_id)
    file_path = json_store.get_output_path() / f"{file_type}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File {file_type}.json not found for task {task_id}")
    
    return FileResponse(
        path=str(file_path),
        filename=f"{task_id}_{file_type}.json",
        media_type="application/json",
    )


@router.delete("/extraction/{task_id}")
async def delete_extraction_task(task_id: str):
    """Delete an extraction task and cleanup resources."""
    task = extraction_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Cleanup temp directory if exists
    if 'temp_dir' in task:
        try:
            shutil.rmtree(task['temp_dir'])
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")
    
    del extraction_tasks[task_id]

    return {"message": "Task deleted successfully"}