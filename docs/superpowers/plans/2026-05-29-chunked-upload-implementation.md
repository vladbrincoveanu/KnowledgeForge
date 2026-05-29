# Chunked Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement chunked ZIP upload (up to 6GB) and extend Git URL extraction with `full_history` support.

**Architecture:** Chunked upload uses a session-based protocol: `POST /upload/start` → multiple `PUT /upload/chunk` → `POST /upload/complete`. Sessions stored in-memory with lazy expiry. Reassembly produces a ZIP fed into the existing `safe_extract_zip()` → `run_c4_extraction()` pipeline. Git URL path gets a new `full_history` field.

**Tech Stack:** FastAPI, Pydantic V2, asyncio.Lock, shutil, hashlib

---

## File Map

| File | Responsibility |
|------|----------------|
| `sources/Api/app/utils/security.py` | Update `MAX_ZIP_UNCOMPRESSED_BYTES` 500MB → 6GB |
| `sources/Api/app/endpoint/v1/routes/code_extraction.py` | All changes: models, session storage, locks, endpoints, bug fix |
| `sources/Api/tests/unit/endpoint/v1/routes/test_code_extraction.py` | Unit tests for new endpoints + full_history |

---

## Task 1: Update MAX_ZIP_UNCOMPRESSED_BYTES

**Files:**
- Modify: `sources/Api/app/utils/security.py:17-18`

- [ ] **Step 1: Change the constant**

```python
# Maximum allowed uncompressed ZIP size (6 GB)
MAX_ZIP_UNCOMPRESSED_BYTES = 6 * 1024 * 1024 * 1024
```

- [ ] **Step 2: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge && git add sources/Api/app/utils/security.py && git commit -m "fix: raise MAX_ZIP_UNCOMPRESSED_BYTES from 500MB to 6GB"
```

---

## Task 2: Add `full_history` to GitHubScanRequest and wire it through

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py:139-182` (GitHubScanRequest model)
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py:587-644` (extract_from_github handler)

- [ ] **Step 1: Add `full_history` field to GitHubScanRequest model (after `token` field, line ~163)**

```python
    full_history: bool = Field(
        default=False,
        description=(
            "Clone with full Git history. Set True for repos > 6GB or when historical "
            "analysis is needed. When False (default), uses --depth 1 for speed."
        ),
    )
```

- [ ] **Step 2: Pass `full_history` to `download_repository()` call in `extract_from_github` (line ~611)**

Change:
```python
        repo_path = GitHubDownloader.download_repository(
            request.github_url,
            output_dir=temp_dir,
            use_git=request.use_git,
            token=request.token or None,
        )
```

To:
```python
        repo_path = GitHubDownloader.download_repository(
            request.github_url,
            output_dir=temp_dir,
            use_git=request.use_git,
            full_history=request.full_history,
            token=request.token or None,
        )
```

- [ ] **Step 3: Add example to model_config json_schema_extra (line ~176)**

Add to the existing `json_schema_extra["examples"]` list:
```python
{
    "github_url": "https://github.com/microservices-demo/microservices-demo",
    "use_git": True,
    "full_history": False,
    "append_mode": False,
}
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import GitHubScanRequest; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add full_history field to GitHubScanRequest"
```

---

## Task 3: Fix temp_dir cleanup bug in `run_c4_extraction` except block

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py:954-964`

- [ ] **Step 1: Add cleanup in the failure except block (after line 962)**

Change the `except (ConnectionError, RuntimeError) as e:` block (lines 954-964) from:

```python
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
```

To:

```python
    except (ConnectionError, RuntimeError) as e:
        logger.error(f"C4 extraction failed for task {task_id}: {e}", exc_info=True)

        task = scan_tasks.get(task_id)
        if task:
            task['status'] = 'failed'
            task['message'] = f'Extraction failed: {str(e)}'
            task.setdefault('errors', []).append(str(e))
            logger.error(f"Task {task_id} failed: {task['message']}")
            # Cleanup temp directory on failure
            if 'temp_dir' in task:
                try:
                    shutil.rmtree(task['temp_dir'])
                except (ConnectionError, RuntimeError) as cleanup_err:
                    logger.warning(f"Failed to cleanup temp directory on failure: {cleanup_err}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "import ast; ast.parse(open('app/endpoint/v1/routes/code_extraction.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "fix: cleanup temp_dir in run_c4_extraction failure path"
```

---

## Task 4: Add upload session storage, locks, and Pydantic models

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py:30` (after existing scan_tasks line)

- [ ] **Step 1: Add session storage dict and per-session lock dict after line 30**

After the existing `# In-memory storage for scan tasks` comment block, add:

```python
# In-memory storage for upload sessions (keyed by session_id)
# Structure per session:
# {
#     "session_id": str,
#     "created_at": datetime,
#     "expires_at": datetime,
#     "filename": str,
#     "total_chunks": int,
#     "expected_size_bytes": int,
#     "expected_sha256": str,
#     "received_chunks": dict[int, int],  # chunk_number -> size_bytes
#     "status": "uploading" | "completed" | "failed" | "expired",
#     "chunk_dir": Path,
# }
upload_sessions: dict[str, dict] = {}

# Per-session asyncio locks to serialize concurrent chunk uploads
upload_session_locks: dict[str, asyncio.Lock] = {}
```

- [ ] **Step 2: Add new Pydantic models for chunked upload (after GitHubScanRequest, around line 183)**

```python
class UploadStartRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    total_chunks: int = Field(..., ge=1, le=30)
    expected_size_bytes: int = Field(..., ge=1, le=6 * 1024 * 1024 * 1024)
    expected_sha256: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="Lowercase hex SHA-256 of the complete ZIP file (64 characters)",
    )


class UploadStartResponse(BaseModel):
    session_id: str
    chunk_urls: list[str]
    expires_at: datetime


class ChunkUploadResponse(BaseModel):
    received: bool
    chunk_number: int
    received_size_bytes: int


class ChunkUploadError(BaseModel):
    error: str
    chunk_number: int
    status: int = 409


class UploadCompleteResponse(BaseModel):
    task_id: str
    status: str
    message: str


class UploadCancelResponse(BaseModel):
    cancelled: bool
    session_id: str


class UploadStatusResponse(BaseModel):
    session_id: str
    status: str
    received_chunks: list[int]
    missing_chunks: list[int]
    total_chunks: int
    expires_at: datetime


class UploadErrorResponse(BaseModel):
    error: str
    session_id: str
```

- [ ] **Step 3: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import UploadStartRequest, UploadStartResponse, ChunkUploadResponse, UploadCompleteResponse, UploadCancelResponse, UploadStatusResponse; print('Models OK')"
```

- [ ] **Step 4: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add upload session storage, locks, and Pydantic models"
```

---

## Task 5: Implement `POST /upload/start`

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py`

- [ ] **Step 1: Add the import for `hashlib` at the top if not present**

Check that `hashlib` is imported. Add `import hashlib` near the other imports if not present.

- [ ] **Step 2: Add helper function `_cleanup_upload_session` after the session dicts (around line 48)**

```python
def _cleanup_upload_session(session_id: str) -> None:
    """Delete chunk directory and remove session from upload_sessions."""
    session = upload_sessions.get(session_id)
    if session and session.get("chunk_dir"):
        try:
            shutil.rmtree(session["chunk_dir"])
        except (OSError, RuntimeError) as e:
            logger.warning(f"Failed to cleanup chunk directory for session {session_id}: {e}")
    upload_sessions.pop(session_id, None)
    upload_session_locks.pop(session_id, None)
```

- [ ] **Step 3: Add the `/upload/start` endpoint (after the GitHubOrgScanRequest model, around line 730)**

```python
@router.post(
    "/upload/start",
    response_model=UploadStartResponse,
    status_code=201,
    summary="Initiate a chunked upload session",
    description="Starts an upload session for a large ZIP file split into chunks.",
    responses={
        201: {"description": "Upload session created"},
        400: {"description": "Invalid request (bad sha256 format, etc.)"},
    },
)
async def upload_start(request: UploadStartRequest):
    session_id = str(uuid.uuid4())
    chunk_dir = Path(tempfile.mkdtemp(prefix=f"kf-chunks_{session_id}_"))
    chunk_dir.chmod(0o700)
    expires_at = datetime.now() + timedelta(hours=1)

    session = {
        "session_id": session_id,
        "created_at": datetime.now(),
        "expires_at": expires_at,
        "filename": request.filename,
        "total_chunks": request.total_chunks,
        "expected_size_bytes": request.expected_size_bytes,
        "expected_sha256": request.expected_sha256,
        "received_chunks": {},
        "status": "uploading",
        "chunk_dir": chunk_dir,
    }
    upload_sessions[session_id] = session
    upload_session_locks[session_id] = asyncio.Lock()

    chunk_urls = [
        f"/api/v1/code/upload/chunk/{session_id}/{i}"
        for i in range(request.total_chunks)
    ]

    return UploadStartResponse(
        session_id=session_id,
        chunk_urls=chunk_urls,
        expires_at=expires_at,
    )
```

Note: Add `timedelta` to the existing `datetime` import on line 11: `from datetime import datetime, timedelta`. Also add `import asyncio` near the top if not present.

- [ ] **Step 4: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import upload_start; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add POST /upload/start endpoint"
```

---

## Task 6: Implement `PUT /upload/chunk/{session_id}/{chunk_number}`

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py`

- [ ] **Step 1: Add the endpoint (after `/upload/start`)**

```python
MAX_CHUNK_BYTES = 200 * 1024 * 1024  # 200 MB


@router.put(
    "/upload/chunk/{session_id}/{chunk_number}",
    response_model=ChunkUploadResponse,
    summary="Upload a single chunk",
    responses={
        200: {"description": "Chunk received"},
        404: {"description": "Session not found"},
        409: {"description": "Chunk already received or concurrent upload"},
        410: {"description": "Session expired"},
        413: {"description": "Chunk too large"},
    },
)
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    background_tasks: BackgroundTasks,
):
    session = upload_sessions.get(session_id)

    # Session not found
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Lazy expiry check
    if datetime.now() > session["expires_at"]:
        _cleanup_upload_session(session_id)
        raise HTTPException(status_code=410, detail="Session expired")

    # Concurrent upload guard
    lock = upload_session_locks.get(session_id)
    if lock is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async with lock:
        # Re-check expiry inside lock
        if datetime.now() > session["expires_at"]:
            _cleanup_upload_session(session_id)
            raise HTTPException(status_code=410, detail="Session expired")

        # Duplicate chunk check
        if chunk_number in session["received_chunks"]:
            return ChunkUploadResponse(
                received=False,
                chunk_number=chunk_number,
                received_size_bytes=session["received_chunks"][chunk_number],
            )

        # Validate chunk number range
        if chunk_number < 0 or chunk_number >= session["total_chunks"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chunk number {chunk_number}; expected 0 to {session['total_chunks'] - 1}",
            )

        # Read chunk from request body (streaming)
        chunk_bytes = await _read_chunk_body()
        chunk_size = len(chunk_bytes)

        # Size check
        if chunk_size > MAX_CHUNK_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Chunk size {chunk_size} exceeds limit {MAX_CHUNK_BYTES}",
            )

        # Write chunk to disk
        chunk_path = session["chunk_dir"] / f"chunk_{chunk_number:06d}"
        with open(chunk_path, "wb") as f:
            f.write(chunk_bytes)
        os.chmod(chunk_path, 0o600)

        session["received_chunks"][chunk_number] = chunk_size
        # Refresh TTL
        session["expires_at"] = datetime.now() + timedelta(hours=1)

        return ChunkUploadResponse(
            received=True,
            chunk_number=chunk_number,
            received_size_bytes=chunk_size,
        )
```

- [ ] **Step 2: Add helper before the endpoint (around line ~750)**

Add `from fastapi import Request` to the imports if not already present. Then add:

```python
async def _read_chunk_body(request: Request) -> bytes:
    """Read entire request body as bytes for chunk uploads."""
    return await request.body()
```

- [ ] **Step 3: Fix the endpoint signature to include request**

```python
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    request: Request,
    background_tasks: BackgroundTasks,
):
    ...
    chunk_bytes = await _read_chunk_body(request)
    ...
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import upload_chunk; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add PUT /upload/chunk endpoint with per-session locking"
```

---

## Task 7: Implement `POST /upload/complete/{session_id}`

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py`

- [ ] **Step 1: Add `POST /upload/complete/{session_id}` endpoint (after chunk upload)**

```python
@router.post(
    "/upload/complete/{session_id}",
    response_model=UploadCompleteResponse,
    status_code=202,
    summary="Finalize chunked upload and start extraction",
    responses={
        202: {"description": "Upload complete, extraction started"},
        400: {"description": "Missing chunks, size mismatch, or SHA256 mismatch"},
        404: {"description": "Session not found"},
        410: {"description": "Session expired"},
    },
)
async def upload_complete(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    session = upload_sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Lazy expiry check
    if datetime.now() > session["expires_at"]:
        _cleanup_upload_session(session_id)
        raise HTTPException(status_code=410, detail="Session expired")

    # Verify all chunks received
    received = set(session["received_chunks"].keys())
    expected = set(range(session["total_chunks"]))
    missing = expected - received

    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing chunks",
                "missing_chunks": sorted(missing),
                "received_chunks": sorted(received),
                "total_chunks": session["total_chunks"],
            },
        )

    # Verify total size
    total_received = sum(session["received_chunks"].values())
    if total_received != session["expected_size_bytes"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "size mismatch",
                "expected_size_bytes": session["expected_size_bytes"],
                "received_size_bytes": total_received,
            },
        )

    # Reassemble
    reassembled_path = Path(tempfile.gettempdir()) / f"kf-reassembled_{session_id}.zip"
    try:
        with open(reassembled_path, "wb") as out_f:
            for i in range(session["total_chunks"]):
                chunk_path = session["chunk_dir"] / f"chunk_{i:06d}"
                with open(chunk_path, "rb") as in_f:
                    out_f.write(in_f.read())

        # SHA256 verification
        sha256_hash = hashlib.sha256()
        with open(reassembled_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192 * 1024), b""):
                sha256_hash.update(chunk)
        computed_hash = sha256_hash.hexdigest()

        if computed_hash != session["expected_sha256"]:
            os.remove(reassembled_path)
            session["status"] = "failed"
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "sha256 mismatch",
                    "expected": session["expected_sha256"],
                    "computed": computed_hash,
                },
            )
    finally:
        # Clean up chunks dir immediately after reassembly attempt
        _cleanup_upload_session(session_id)

    # Extract and start C4 extraction
    task_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.mkdtemp(prefix=f"repo_{task_id}_"))
    extract_dir = temp_dir / "extracted"
    extract_dir.mkdir()

    try:
        safe_extract_zip(reassembled_path, extract_dir)
    except ValueError as exc:
        os.remove(reassembled_path)
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        # Delete reassembled ZIP after extraction starts (or on failure)
        try:
            os.remove(reassembled_path)
        except OSError:
            pass

    # Find repo root
    subdirs = list(extract_dir.iterdir())
    repo_path = extract_dir
    if len(subdirs) == 1 and subdirs[0].is_dir():
        repo_path = subdirs[0]

    scan_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0.0,
        "message": "Chunked upload complete, scan queued",
        "created_at": datetime.now(),
        "repo_path": str(repo_path),
        "temp_dir": str(temp_dir),
        "errors": [],
    }

    background_tasks.add_task(
        run_c4_extraction,
        task_id,
        repo_path,
    )

    return UploadCompleteResponse(
        task_id=task_id,
        status="pending",
        message="ZIP reassembled and scan queued",
    )
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import upload_complete; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add POST /upload/complete endpoint with reassembly and SHA256 validation"
```

---

## Task 8: Implement `DELETE /upload/session/{session_id}` and `GET /upload/session/{session_id}/status`

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py`

- [ ] **Step 1: Add DELETE endpoint (after upload_complete)**

```python
@router.delete(
    "/upload/session/{session_id}",
    response_model=UploadCancelResponse,
    summary="Cancel an upload session",
    responses={
        200: {"description": "Session cancelled"},
        404: {"description": "Session not found"},
    },
)
async def upload_cancel(session_id: str):
    if session_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    _cleanup_upload_session(session_id)

    return UploadCancelResponse(cancelled=True, session_id=session_id)
```

- [ ] **Step 2: Add GET status endpoint (after upload_cancel)**

```python
@router.get(
    "/upload/session/{session_id}/status",
    response_model=UploadStatusResponse,
    summary="Get upload session status",
    responses={
        200: {"description": "Session status"},
        404: {"description": "Session not found"},
        410: {"description": "Session expired"},
    },
)
async def upload_status(session_id: str):
    session = upload_sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if datetime.now() > session["expires_at"]:
        _cleanup_upload_session(session_id)
        raise HTTPException(status_code=410, detail="Session expired")

    received = set(session["received_chunks"].keys())
    expected = set(range(session["total_chunks"]))
    missing = sorted(expected - received)

    return UploadStatusResponse(
        session_id=session_id,
        status=session["status"],
        received_chunks=sorted(received),
        missing_chunks=missing,
        total_chunks=session["total_chunks"],
        expires_at=session["expires_at"],
    )
```

- [ ] **Step 3: Verify build**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -c "from app.endpoint.v1.routes.code_extraction import upload_cancel, upload_status; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py && git commit -m "feat: add DELETE and GET status endpoints for upload sessions"
```

---

## Task 9: Add unit tests

**Files:**
- Modify: `sources/Api/tests/unit/endpoint/v1/routes/test_code_extraction.py`

- [ ] **Step 1: Add tests for `full_history` field**

```python
class TestGitHubScanRequestFullHistory:
    def test_full_history_default_false(self):
        request = GitHubScanRequest(github_url="https://github.com/owner/repo")
        assert request.full_history is False

    def test_full_history_explicit_true(self):
        request = GitHubScanRequest(github_url="https://github.com/owner/repo", full_history=True)
        assert request.full_history is True

    def test_full_history_rejected_if_not_bool(self):
        with pytest.raises(ValidationError):
            GitHubScanRequest(github_url="https://github.com/owner/repo", full_history="yes")
```

- [ ] **Step 2: Add tests for upload session lifecycle**

```python
from tests.unit.endpoint.v1.routes.test_code_extraction import client, tmp_path


class TestUploadStart:
    def test_upload_start_valid_request(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 629145600,  # 600 MB
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert len(data["chunk_urls"]) == 3
        assert data["chunk_urls"][0].endswith("/api/v1/code/upload/chunk/{session_id}/0")

    def test_upload_start_invalid_sha256_format(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 1024,
                "expected_sha256": "not-a-valid-sha256",
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_upload_start_total_chunks_exceeds_limit(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 31,  # max is 30
                "expected_size_bytes": 1024,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        assert response.status_code == 422


class TestUploadChunk:
    def test_upload_chunk_session_not_found(self, client):
        response = client.put(
            "/api/v1/code/upload/chunk/invalid-session/0",
            content=b"test chunk data",
        )
        assert response.status_code == 404

    def test_upload_chunk_too_large(self, client):
        # Start session
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 1024,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        # Upload oversized chunk (201 MB > 200 MB limit)
        large_chunk = b"x" * (201 * 1024 * 1024)
        response = client.put(
            f"/api/v1/code/upload/chunk/{session_id}/0",
            content=large_chunk,
        )
        assert response.status_code == 413

    def test_upload_chunk_duplicate(self, client):
        # Start session
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 5,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        # Upload first chunk
        response1 = client.put(
            f"/api/v1/code/upload/chunk/{session_id}/0",
            content=b"hello",
        )
        assert response1.status_code == 200
        assert response1.json()["received"] is True

        # Upload same chunk again
        response2 = client.put(
            f"/api/v1/code/upload/chunk/{session_id}/0",
            content=b"hello",
        )
        assert response2.status_code == 200
        assert response2.json()["received"] is False


class TestUploadComplete:
    def test_upload_complete_missing_chunks(self, client):
        # Start session with 3 chunks, upload only 1
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 15,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        # Upload chunk 0 only
        client.put(f"/api/v1/code/upload/chunk/{session_id}/0", content=b"01234")

        # Try to complete
        response = client.post(f"/api/v1/code/upload/complete/{session_id}")
        assert response.status_code == 400
        assert "missing_chunks" in response.json()["detail"]["error"]


class TestUploadCancel:
    def test_upload_cancel_success(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 5,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        response = client.delete(f"/api/v1/code/upload/session/{session_id}")
        assert response.status_code == 200
        assert response.json()["cancelled"] is True

        # Verify session gone
        status_resp = client.get(f"/api/v1/code/upload/session/{session_id}/status")
        assert status_resp.status_code == 404


class TestUploadStatus:
    def test_upload_status_shows_missing_chunks(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 15,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        # Upload chunks 0 and 2
        client.put(f"/api/v1/code/upload/chunk/{session_id}/0", content=b"01234")
        client.put(f"/api/v1/code/upload/chunk/{session_id}/2", content=b"90123")

        status = client.get(f"/api/v1/code/upload/session/{session_id}/status")
        assert status.status_code == 200
        data = status.json()
        assert set(data["received_chunks"]) == {0, 2}
        assert data["missing_chunks"] == [1]
```

Note: These tests use the existing `client` fixture from the test file. Verify the fixture exists and supports `content=` for raw bytes (FastAPI TestClient supports this).

- [ ] **Step 3: Run tests**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/endpoint/v1/routes/test_code_extraction.py -v --tb=short 2>&1 | head -100
```

Fix any failures before proceeding.

- [ ] **Step 4: Commit**

```bash
git add sources/Api/tests/unit/endpoint/v1/routes/test_code_extraction.py && git commit -m "test: add unit tests for chunked upload endpoints and full_history field"
```

---

## Task 10: Smoke test (integration)

**Files:**
- No file changes — this is a verification step

- [ ] **Step 1: Start the API server**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 main.py &
sleep 3
```

- [ ] **Step 2: Test the full flow with a real small ZIP**

Create a test ZIP and split it:
```bash
# Create a small test repo
mkdir /tmp/test-repo && echo "hello" > /tmp/test-repo/README.md
cd /tmp && zip -r test-repo.zip test-repo

# Calculate SHA256
sha256sum test-repo.zip

# Split into chunks (e.g., 1 byte per chunk for testing — or use small chunk size)
split -b 100 test-repo.zip chunk_
```

Then test with curl:
```bash
# Start session
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/code/upload/start \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.zip","total_chunks":3,"expected_size_bytes":1234,"expected_sha256":"PLACEHOLDER_SHA256"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Upload chunks (adapt chunk file names from split output)
curl -X PUT "http://localhost:8000/api/v1/code/upload/chunk/$SESSION/0" --data-binary @chunk_aa
curl -X PUT "http://localhost:8000/api/v1/code/upload/chunk/$SESSION/1" --data-binary @chunk_ab
curl -X PUT "http://localhost:8000/api/v1/code/upload/chunk/$SESSION/2" --data-binary @chunk_ac

# Check status
curl "http://localhost:8000/api/v1/code/upload/session/$SESSION/status"

# Complete (will fail SHA256 mismatch since we used placeholder — expected)
curl -X POST "http://localhost:8000/api/v1/code/upload/complete/$SESSION"
```

- [ ] **Step 3: Kill test server**

```bash
pkill -f "python3 main.py"
```

---

## Task 11: Run full test suite

- [ ] **Step 1: Run API unit tests**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge && make tests 2>&1 | tail -50
```

- [ ] **Step 2: Run type check**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m mypy app/ --ignore-missing-imports 2>&1 | grep -E "(error|warning)" | head -20
```

- [ ] **Step 3: Fix any issues found**

---

## Spec Coverage Check

| Spec Section | Task |
|--------------|------|
| Git URL `full_history` field | Task 2 |
| `MAX_ZIP_UNCOMPRESSED_BYTES` 6GB | Task 1 |
| `POST /upload/start` | Task 5 |
| `PUT /upload/chunk/{session_id}/{chunk_number}` | Task 6 |
| `POST /upload/complete/{session_id}` | Task 7 |
| `DELETE /upload/session/{session_id}` | Task 8 |
| `GET /upload/session/{session_id}/status` | Task 8 |
| Per-session locking | Tasks 5, 6 |
| Lazy expiry | Tasks 5, 6, 7, 8 |
| SHA256 required validation | Tasks 5, 6 (model), 7 (verify) |
| Size mismatch detection | Task 7 |
| Duplicate chunk rejection | Task 6 |
| Chunk cleanup on expiry | `_cleanup_upload_session` in Tasks 5, 6, 7, 8 |
| Temp dir cleanup on extraction failure | Task 3 |
| Unit tests | Task 9 |

**All spec requirements covered.**

---

## Type Consistency Check

- `UploadStartRequest.expected_sha256`: `str` matching `^[a-f0-9]{64}$` — used as hex in `upload_complete`
- `UploadCompleteResponse`: matches `ScanResponse` pattern (task_id, status, message)
- `ChunkUploadResponse.received`: `bool` — `True` for success, `False` for already received
- Session `status` field: `Literal["uploading", "completed", "failed", "expired"]`
- All datetime fields: `datetime` (not `str`)

**Types consistent across tasks.**