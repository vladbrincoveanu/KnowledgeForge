"""Code extraction endpoints for repository scanning."""

import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.infrastructure.llm.llm_manager import LLMManager
from app.services.code_extraction.c4_extractor import C4ArchitectureExtractor
from app.utils.github_downloader import GitHubDownloader
from app.endpoint.v1.dependencies import get_llm_manager
from app.utils.security import safe_extract_zip, validate_local_repo_path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["code-extraction"])
ARCHITECTURE_CHAT_MAX_TOKENS = int(os.getenv("ARCHITECTURE_CHAT_MAX_TOKENS", "1024"))

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
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to save C4 architecture to JSON: {e}", exc_info=True)


def _load_latest_c4_from_json() -> dict:
    """Load the most recent C4 architecture from JSON file.
    
    For batch extractions, loads the aggregated result.
    Falls back to merging multiple batch files if needed (legacy behavior).
    """
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
            data = json.load(f)
            
        # Log statistics for debugging
        context_level = data.get('context_level', {})
        systems = context_level.get('systems', [])
        logger.info(f"Loaded {len(systems)} systems from {latest_file.name}")
        
        return data
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to load C4 architecture from JSON: {e}", exc_info=True)
        return {}


def _load_default_c4_from_json() -> dict:
    """Load the bundled demo architecture used for cold starts."""
    try:
        api_root = Path(__file__).resolve().parents[4]
        demo_file = api_root / "c4_architecture.json"
        if not demo_file.exists():
            logger.warning(f"Default demo file does not exist: {demo_file}")
            return {}

        with open(demo_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to load bundled demo C4 JSON: {e}", exc_info=True)
        return {}


def _load_latest_runtime_c4() -> dict:
    """Return the latest completed runtime extraction kept in memory."""
    completed_tasks = [
        task for task in scan_tasks.values()
        if task.get('status') == 'completed' and task.get('c4_architecture')
    ]
    if not completed_tasks:
        return {}

    latest_task = max(
        completed_tasks,
        key=lambda task: task.get('completed_at') or task.get('created_at') or datetime.min,
    )
    return latest_task.get('c4_architecture') or {}


class ScanRequest(BaseModel):
    """Request model for local repository C4 scan."""

    repo_path: Optional[str] = Field(
        None,
        description="Absolute local path to the repository. Allowed prefixes: /tmp, /repos, /data.",
        examples=["/repos/my-platform"],
    )
    use_c4_model: bool = Field(
        default=True,
        description="Use the C4 Model extractor (recommended). Set False for a legacy flat extraction.",
    )
    max_components_per_domain: int = Field(
        default=10,
        description="Component threshold above which components are grouped by domain.",
        ge=1,
        le=100,
    )


class GitHubScanRequest(BaseModel):
    """Request model for GitHub-based C4 scan."""

    github_url: str = Field(
        ...,
        description="HTTPS URL of the GitHub repository to scan.",
        examples=["https://github.com/microservices-demo/microservices-demo"],
    )
    use_git: bool = Field(
        default=True,
        description="Clone via `git clone`. Set False to use archive download.",
    )
    max_components_per_domain: int = Field(
        default=10,
        description="Component threshold above which components are grouped by domain.",
        ge=1,
        le=100,
    )
    append_mode: bool = Field(
        default=True,
        description=(
            "Append results to existing C4 data (True) or clear all stored data first (False)."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "github_url": "https://github.com/microservices-demo/microservices-demo",
                    "use_git": True,
                    "append_mode": False,
                }
            ]
        }
    }


class ScanResponse(BaseModel):
    """Response model for C4 scan operations."""

    task_id: str = Field(..., description="Unique task identifier (UUID).", examples=["d4e5f6a7-..."])
    status: str = Field(..., description="Initial task status. Always 'pending'.", examples=["pending"])
    message: str = Field(..., description="Human-readable status message.")
    created_at: datetime = Field(..., description="UTC timestamp when the task was created.")


class ScanStatusResponse(BaseModel):
    """Response model for C4 scan status."""

    task_id: str = Field(..., description="Task identifier.")
    status: str = Field(
        ...,
        description="Task lifecycle state: pending | scanning | completed | failed.",
        examples=["completed"],
    )
    progress: float = Field(..., description="Fractional progress 0.0–1.0.", examples=[1.0])
    message: str = Field(..., description="Latest status message.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    completed_at: Optional[datetime] = Field(None, description="UTC completion timestamp.")
    containers_count: int = Field(0, description="Number of C4 containers extracted.")
    components_count: int = Field(0, description="Number of C4 components extracted.")
    external_deps_count: int = Field(0, description="Number of external dependencies detected.")
    errors: list[str] = Field(default_factory=list, description="Non-fatal errors encountered.")
    extraction_mode: str = Field("c4_model", description="Extraction mode used (c4_model or legacy).")


class NodeDescribeRequest(BaseModel):
    """Request model for node description."""
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    level: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    container_meta: Optional[dict[str, Any]] = Field(default=None, alias="containerMeta")
    file: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class EdgeDescribeRequest(BaseModel):
    """Request model for edge description."""
    id: Optional[str] = None
    source: Optional[str] = None
    target: Optional[str] = None
    label: Optional[str] = None
    relationship_type: Optional[str] = Field(default=None, alias="relationshipType")
    protocol: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class ArchitectureChatMessage(BaseModel):
    """Conversation turn for architecture chat."""

    role: str = Field(..., description="Chat role, usually user or assistant.")
    content: str = Field(..., description="Message text.")


class ArchitectureChatRequest(BaseModel):
    """Request model for architecture-aware chat."""

    message: str = Field(..., description="Latest user message for the chat.")
    history: list[ArchitectureChatMessage] = Field(
        default_factory=list,
        description="Recent chat history, oldest to newest.",
    )
    selection: Optional[dict[str, Any]] = Field(
        default=None,
        description="Currently selected node or edge context from the viewer.",
    )
    architecture: Optional[dict[str, Any]] = Field(
        default=None,
        description="High-level architecture summary from the viewer state.",
    )
    prefer_heuristic: bool = Field(
        default=False,
        alias="preferHeuristic",
        description="Skip the LLM and return the deterministic fallback immediately.",
    )
    stream: bool = Field(
        default=False,
        description="Return newline-delimited JSON deltas instead of a single message.",
    )

    class Config:
        allow_population_by_field_name = True


def _build_node_prompt(payload: NodeDescribeRequest) -> str:
    context = {
        "name": payload.name,
        "type": payload.type,
        "level": payload.level,
        "file": payload.file,
        "attributes": payload.attributes or {},
        "container_meta": payload.container_meta or {},
    }

    return (
        "You are a software architecture assistant. "
        "Given the following node details from a C4 diagram, "
        "write 1-2 concise sentences describing what this node is used for. "
        "If details are limited, infer from name, type, technology, deployment, and path. "
        "Avoid speculation beyond the data.\n\n"
        f"Node details: {json.dumps(context, ensure_ascii=False)}"
    )


def _build_edge_prompt(payload: EdgeDescribeRequest) -> str:
    context = {
        "source": payload.source,
        "target": payload.target,
        "relationship_type": payload.relationship_type,
        "protocol": payload.protocol or payload.label,
    }

    return (
        "You are a software architecture assistant. "
        "Given the following relationship between two C4 nodes, "
        "write 1 concise sentence describing what the interaction represents. "
        "If protocol is provided, mention it.\n\n"
        f"Edge details: {json.dumps(context, ensure_ascii=False)}"
    )


def _compact_json(value: Any, max_chars: int = 2500) -> str:
    """Serialize context payloads without letting prompts grow unbounded."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)

    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _format_alternatives_for_fallback(alternatives: list[dict[str, Any]]) -> str:
    """Render provider alternatives for heuristic chat answers."""
    formatted: list[str] = []
    for alternative in alternatives[:3]:
        provider = alternative.get("provider") or "Unknown provider"
        tiers = " / ".join(
            str(value)
            for value in [
                alternative.get("price_tier"),
                alternative.get("performance_tier"),
            ]
            if value
        )
        profile = alternative.get("profile") or alternative.get("notes")
        parts = [provider]
        if tiers:
            parts.append(f"({tiers})")
        if profile:
            parts.append(f"- {profile}")
        formatted.append(" ".join(parts))
    return "; ".join(formatted)


def _build_architecture_chat_prompt(payload: ArchitectureChatRequest) -> str:
    """Create a compact prompt for architecture-aware chat."""
    recent_history = [
        {"role": item.role, "content": item.content}
        for item in payload.history[-6:]
        if item.content
    ]

    return (
        "You are a concise software architecture assistant embedded in a C4 viewer. "
        "Answer the user's question using only the provided architecture context. "
        "Prefer business-facing language at context level. "
        "If the answer is not supported by the supplied data, say that directly. "
        "Keep answers short and practical.\n\n"
        f"Architecture summary: {_compact_json(payload.architecture or {})}\n"
        f"Current selection: {_compact_json(payload.selection or {})}\n"
        f"Recent conversation: {_compact_json(recent_history)}\n"
        f"User question: {payload.message.strip()}"
    )


def _build_architecture_chat_fallback(payload: ArchitectureChatRequest) -> str:
    """Return a deterministic fallback when no LLM is available."""
    architecture = payload.architecture or {}
    selection = payload.selection or {}
    system = architecture.get("system") or {}
    system_name = system.get("name") or "the system"
    selected_level = architecture.get("selectedLevel") or "current"
    message_lower = payload.message.strip().lower()

    if selection.get("kind") == "node":
        node = selection.get("node") or {}
        attrs = node.get("attributes") or {}
        node_name = node.get("name") or node.get("label") or "This node"
        description = (
            node.get("description")
            or attrs.get("description")
            or attrs.get("purpose")
        )
        alternatives = attrs.get("provider_alternatives") or []

        if alternatives and any(
            keyword in message_lower
            for keyword in ["alternative", "alternatives", "compare", "cheaper", "price", "performance"]
        ):
            return (
                f"Known alternatives for {node_name}: "
                f"{_format_alternatives_for_fallback(alternatives)}. "
                "I do not have a model-backed recommendation right now, but these are the seeded review options."
            )

        if description:
            return f"{node_name} belongs to {system_name}. {description}"

        node_type = node.get("type") or "node"
        return (
            f"{node_name} is a {node_type} in {system_name}. "
            "Ask about its responsibilities, ownership, or relationships for more detail."
        )

    if selection.get("kind") == "edge":
        edge = selection.get("edge") or {}
        description = edge.get("description")
        if description:
            return str(description)

        source = edge.get("source") or "Source"
        target = edge.get("target") or "Target"
        label = edge.get("label") or "interacts with"
        return f"{source} {label} {target}."

    counts = architecture.get("counts") or {}
    node_count = counts.get("nodes")
    edge_count = counts.get("edges")
    count_summary = []
    if node_count is not None:
        count_summary.append(f"{node_count} nodes")
    if edge_count is not None:
        count_summary.append(f"{edge_count} relationships")
    suffix = f" It currently shows {', '.join(count_summary)}." if count_summary else ""

    return (
        f"You are looking at {system_name} on the {selected_level} level."
        f"{suffix} Select a node or edge to get more specific answers."
    )


def _iter_text_deltas(text: str) -> Iterator[str]:
    """Yield small word-like chunks for typing-style streaming."""
    for match in re.finditer(r"\S+\s*", text):
        yield match.group(0)


def _stream_architecture_chat_response(
    payload: ArchitectureChatRequest,
) -> Iterator[str]:
    """Stream architecture chat as newline-delimited JSON chunks."""
    prompt = _build_architecture_chat_prompt(payload)
    llm_manager = get_llm_manager()

    if llm_manager and not payload.prefer_heuristic:
        try:
            received_llm_delta = False
            for delta in llm_manager.stream_text(
                prompt,
                max_tokens=ARCHITECTURE_CHAT_MAX_TOKENS,
                temperature=0.2,
            ):
                if not delta:
                    continue
                received_llm_delta = True
                yield json.dumps(
                    {"type": "delta", "delta": delta, "source": "llm"},
                    ensure_ascii=False,
                ) + "\n"
            if received_llm_delta:
                yield json.dumps(
                    {"type": "done", "source": "llm"},
                    ensure_ascii=False,
                ) + "\n"
                return
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Architecture chat streaming failed: %s", exc)

    fallback_message = _build_architecture_chat_fallback(payload)
    for delta in _iter_text_deltas(fallback_message):
        yield json.dumps(
            {"type": "delta", "delta": delta, "source": "heuristic"},
            ensure_ascii=False,
        ) + "\n"
    yield json.dumps(
        {"type": "done", "source": "heuristic"},
        ensure_ascii=False,
    ) + "\n"


@router.post(
    "/upload-repo",
    response_model=ScanResponse,
    status_code=202,
    summary="Upload a repository ZIP for C4 extraction",
    description=(
        "Upload a ZIP archive and start an asynchronous C4 architecture extraction.\n\n"
        "**Security:** rejects path-traversal entries, symlinks, and ZIP bombs (>500 MB).\n\n"
        "Poll `GET /api/v1/code/scan/{task_id}` for progress, "
        "then `GET /api/v1/code/architecture` for results."
    ),
    responses={
        202: {"description": "ZIP accepted and C4 scan queued"},
        400: {"description": "Not a ZIP file, or ZIP failed security validation"},
        500: {"description": "Internal error during upload or scan startup"},
    },
)
async def upload_repository(
    file: UploadFile = File(..., description="ZIP archive of the repository to scan"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Upload a repository ZIP archive and start C4 extraction (async — returns task_id immediately)."""
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    try:
        # Create task
        task_id = str(uuid.uuid4())

        # Save uploaded file using a safe, server-generated filename
        temp_dir = Path(tempfile.mkdtemp(prefix=f"repo_{task_id}_"))
        zip_path = temp_dir / f"{task_id}.zip"

        with open(zip_path, 'wb') as f:
            content = await file.read()
            f.write(content)

        # Extract ZIP safely (rejects path traversal, symlinks, zip bombs)
        extract_dir = temp_dir / 'extracted'
        extract_dir.mkdir()

        try:
            safe_extract_zip(zip_path, extract_dir)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        
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


@router.post(
    "/extract-from-github",
    response_model=ScanResponse,
    status_code=202,
    summary="Extract C4 architecture from a GitHub repository",
    description=(
        "Downloads a GitHub repository and runs C4 extraction **synchronously** during "
        "the request (download phase), then hands the scan off to a background task.\n\n"
        "**C4 levels extracted:** Context → Container → Component → Code\n\n"
        "Results are merged into `GET /api/v1/code/architecture` (append_mode=True by default).\n\n"
        "Set `GITHUB_TOKEN` env var for higher GitHub API rate limits (5000 req/h vs 60 req/h)."
    ),
    responses={
        202: {"description": "Repository downloaded and C4 scan queued"},
        400: {"description": "Invalid GitHub URL"},
        500: {"description": "Repository download failed"},
    },
)
async def extract_from_github(
    request: GitHubScanRequest,
    background_tasks: BackgroundTasks,
):
    """Download a GitHub repository and start C4 extraction (download is synchronous, scan is async)."""
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


class GitHubOrgScanRequest(BaseModel):
    """Request to scan all repositories from a GitHub user/organization."""
    github_username: str = Field(..., description="GitHub username or organization name")
    include_forks: bool = Field(default=False, description="Include forked repositories")
    max_repos: int = Field(default=10, description="Maximum repositories to scan")
    append_mode: bool = Field(default=True, description="Append to existing data")


@router.post("/extract-from-github-org", response_model=ScanResponse)
async def extract_from_github_org(
    request: GitHubOrgScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Fetch all public repositories from a GitHub user/org and extract them.

    Note: Supports GitHub token via GITHUB_TOKEN env var for higher rate limits.
    Unauthenticated: 60 requests/hour | Authenticated: 5000 requests/hour
    """
    import requests
    import os
    import re

    # Clean username - extract from URL if provided
    username = request.github_username.strip()
    
    # Remove GitHub URL prefix if present
    # Handles: https://github.com/username, github.com/username, @username
    github_url_pattern = r'(?:https?://)?(?:www\.)?github\.com/([^/\s?#]+)'
    match = re.search(github_url_pattern, username, re.IGNORECASE)
    if match:
        username = match.group(1)
    
    # Remove @ symbol if present
    username = username.lstrip('@')
    
    if not username:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub username or organization"
        )

    # Check for GitHub token
    github_token = os.getenv('GITHUB_TOKEN')
    headers = {}
    if github_token:
        headers['Authorization'] = f'token {github_token}'

    # Fetch repos from GitHub API
    repos_url = f'https://api.github.com/users/{username}/repos'
    params = {
        'type': 'all',
        'sort': 'updated',
        'per_page': min(request.max_repos, 100),
    }

    try:
        # Increased timeout from 10s to 30s
        logger.info(f"Fetching repos from GitHub for user: {username}")
        response = requests.get(repos_url, params=params, headers=headers, timeout=30)
        logger.info(f"GitHub API responded with status: {response.status_code}")
        response.raise_for_status()
        repos = response.json()
        logger.info(f"Retrieved {len(repos)} repositories from GitHub")

        # Filter out forks if requested
        if not request.include_forks:
            repos = [r for r in repos if not r.get('fork', False)]
            logger.info(f"After filtering forks: {len(repos)} repositories")

        # Limit to max_repos
        repos = repos[:request.max_repos]

        if not repos:
            raise HTTPException(
                status_code=404,
                detail=f"No repositories found for '{username}'"
            )

        # Create batch task
        task_id = str(uuid.uuid4())
        repo_urls = [r['html_url'] for r in repos]
        
        logger.info(f"Creating batch extraction task {task_id} for {len(repo_urls)} repositories")

        scan_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0.0,
            'message': f'Found {len(repo_urls)} repositories',
            'created_at': datetime.now(),
            'total_repos': len(repo_urls),
            'completed_repos': 0,
            'repo_urls': repo_urls,
            'errors': [],
        }

        # Queue batch extraction
        logger.info(f"Queuing background task for batch extraction of {len(repo_urls)} repos")
        background_tasks.add_task(
            run_batch_extraction,
            task_id,
            repo_urls,
            request.append_mode,
        )

        logger.info(f"Returning response for task {task_id}")
        return ScanResponse(
            task_id=task_id,
            status='pending',
            message=f'Queued {len(repo_urls)} repositories for extraction',
            created_at=datetime.now(),
        )

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"GitHub user/org '{username}' not found"
            )
        elif e.response.status_code == 403:
            # Check if it's rate limit or access denied
            remaining = e.response.headers.get('X-RateLimit-Remaining', 'unknown')
            if remaining == '0':
                reset_time = e.response.headers.get('X-RateLimit-Reset', '')
                msg = "GitHub API rate limit exceeded."
                if github_token:
                    msg += " (authenticated: 5000/hour)"
                else:
                    msg += " (unauthenticated: 60/hour). Set GITHUB_TOKEN env var for higher limits."
                raise HTTPException(status_code=429, detail=msg)
            else:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to '{username}'. Repository may be private."
                )
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")
    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail=f"GitHub API request timed out after 30 seconds. Try again or reduce max_repos."
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")


async def run_batch_extraction(task_id: str, repo_urls: list[str], append_mode: bool):
    """Background task to extract multiple repositories sequentially."""
    total = len(repo_urls)

    # For batch operations, we want to append all repos together
    # First extraction clears DB if append_mode=False, subsequent ones always append
    should_clear_db = not append_mode
    
    for idx, repo_url in enumerate(repo_urls):
        try:
            scan_tasks[task_id]['message'] = f'Extracting {idx + 1}/{total}: {repo_url}'
            scan_tasks[task_id]['progress'] = idx / total
            scan_tasks[task_id]['completed_repos'] = idx

            # Download repository
            temp_dir = Path(tempfile.mkdtemp(prefix=f"batch_{task_id}_{idx}_"))
            repo_path = GitHubDownloader.download_repository(
                repo_url,
                output_dir=temp_dir,
                use_git=True
            )

            # Run extraction with same task_id (will aggregate all repos)
            # Only clear DB on first repo if append_mode=False
            await run_c4_extraction(
                task_id=task_id,  # Use same task_id for all repos
                repo_path=repo_path,
                append_mode=(idx > 0) or append_mode,  # Append after first repo
            )

            scan_tasks[task_id]['completed_repos'] = idx + 1

            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Failed to extract {repo_url}: {e}")
            scan_tasks[task_id].setdefault('errors', []).append({
                'repo_url': repo_url,
                'error': str(e),
            })

    scan_tasks[task_id]['status'] = 'completed'
    scan_tasks[task_id]['progress'] = 1.0
    scan_tasks[task_id]['message'] = f'Completed {total} repositories'


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

    try:
        repo_path = validate_local_repo_path(
            request.repo_path,
            allowed_prefixes=["/tmp", "/repos", "/data", "/cms", "/app/data", "/app/sources/demo"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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

        # Save to JSON file
        _save_c4_to_json(task_id, c4_architecture)

        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")
        
        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'C4 extraction completed successfully'
        task['completed_at'] = datetime.now()
        
        logger.info(f"C4 extraction completed for task {task_id}")
        
        # Cleanup temp directory if exists
        if 'temp_dir' in task:
            try:
                shutil.rmtree(task['temp_dir'])
            except (ConnectionError, RuntimeError) as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
    
    except (ConnectionError, RuntimeError) as e:
        logger.error(f"C4 extraction failed for task {task_id}: {e}", exc_info=True)
        
        task = scan_tasks.get(task_id)
        if task:
            task['status'] = 'failed'
            task['message'] = f'Extraction failed: {str(e)}'
            task.setdefault('errors', []).append(str(e))
            logger.error(f"Task {task_id} failed: {task['message']}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")


@router.get(
    "/scan/{task_id}",
    response_model=ScanStatusResponse,
    summary="Poll C4 scan task status",
    description="Returns the current status and progress of a C4 extraction task.",
    responses={
        200: {"description": "Task status"},
        404: {"description": "Task not found"},
    },
)
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


@router.get(
    "/architecture",
    summary="Retrieve the latest C4 architecture model",
    description=(
        "Returns the current C4 architecture model.\n\n"
        "On a cold start, the bundled OmniPay demo is returned by default. "
        "Once a user runs a scan in the current backend session, the latest "
        "completed extraction is returned instead.\n\n"
        "**Response shape:**\n"
        "```\n"
        "{\n"
        "  c4_model_version: string,\n"
        "  system_context: { name, purpose, languages, frameworks, external_dependencies, … },\n"
        "  containers: [ { id, name, type, technology, endpoint, … } ],\n"
        "  components: [ { id, name, type, file_path, … } ],\n"
        "  context_level: { entities, relationships },\n"
        "  relationships: { … }\n"
        "}\n"
        "```\n\n"
        "Returns an empty skeleton only if both the bundled demo and runtime data are unavailable."
    ),
    responses={
        200: {"description": "C4 architecture model (may be empty skeleton)"},
        500: {"description": "Failed to load architecture data"},
    },
)
async def get_code_architecture():
    """
    Get the active C4 architecture payload.

    Bundled demo (Airbyte) is the default. Runtime extractions are only used
    when explicitly requested via a scan task.
    """
    try:
        c4_data = _load_default_c4_from_json()
        if not c4_data:
            c4_data = _load_latest_runtime_c4()
        if not c4_data:
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


@router.post(
    "/describe/node",
    summary="Generate an LLM description for a C4 node",
    description=(
        "Calls the configured LLM to produce a 1-2 sentence description of a C4 node. "
        "Falls back to a heuristic description when no LLM is available."
    ),
    responses={
        200: {"description": "Description generated (field `source`: llm | heuristic)"},
    },
)
async def describe_node(request: NodeDescribeRequest):
    """Generate a short description for a C4 node."""
    llm_manager = get_llm_manager()
    prompt = _build_node_prompt(request)

    if llm_manager:
        response = llm_manager.generate_text(prompt, max_tokens=120, temperature=0.3)
        if response:
            return {"description": response.strip(), "source": "llm"}

    name = request.name or "This node"
    node_type = request.type or "component"
    file_hint = f" in {request.file}" if request.file else ""
    container_type = None
    if request.container_meta and isinstance(request.container_meta, dict):
        container_type = request.container_meta.get("container_type")

    description = f"{name} is a {container_type or node_type} within the system{file_hint}."
    return {"description": description, "source": "heuristic"}


@router.post(
    "/describe/edge",
    summary="Generate an LLM description for a C4 edge",
    description=(
        "Calls the configured LLM to produce a 1-sentence description of a C4 relationship. "
        "Falls back to a heuristic description when no LLM is available."
    ),
    responses={
        200: {"description": "Description generated (field `source`: llm | heuristic)"},
    },
)
async def describe_edge(request: EdgeDescribeRequest):
    """Generate a short description for a C4 edge."""
    llm_manager = get_llm_manager()
    prompt = _build_edge_prompt(request)

    if llm_manager:
        response = llm_manager.generate_text(prompt, max_tokens=80, temperature=0.3)
        if response:
            return {"description": response.strip(), "source": "llm"}

    source = request.source or "Source"
    target = request.target or "Target"
    rel = request.relationship_type or "interaction"
    protocol = request.protocol or request.label
    protocol_text = f" over {protocol}" if protocol else ""
    description = f"{source} {rel} {target}{protocol_text}."
    return {"description": description, "source": "heuristic"}


@router.post(
    "/chat/context",
    summary="Chat with the current architecture context",
    description=(
        "Uses the current architecture summary, current viewer selection, and recent "
        "chat turns to answer a question about the diagram. Falls back to a deterministic "
        "response when no LLM is configured."
    ),
    responses={
        200: {"description": "Architecture chat response (`source`: llm | heuristic)"},
    },
)
async def chat_with_architecture_context(request: ArchitectureChatRequest):
    """Answer a chat question using the current viewer context."""
    if request.stream:
        return StreamingResponse(
            _stream_architecture_chat_response(request),
            media_type="application/x-ndjson",
        )

    prompt = _build_architecture_chat_prompt(request)
    llm_manager = get_llm_manager()

    if llm_manager and not request.prefer_heuristic:
        try:
            response = llm_manager.generate_text(
                prompt,
                max_tokens=ARCHITECTURE_CHAT_MAX_TOKENS,
                temperature=0.2,
                use_cache=False,
            )
            if response:
                return {"message": response.strip(), "source": "llm"}
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Architecture chat LLM call failed: %s", exc)

    return {
        "message": _build_architecture_chat_fallback(request),
        "source": "heuristic",
    }
