# Chunked Upload & Extended Git URL Extraction Design

**Date:** 2026-05-28
**Status:** Draft
**Project:** KnowledgeForge

---

## 1. Overview

Two complementary upload paths to support repositories up to 6GB:

1. **Git URL extraction** (existing `/extract-from-github` extended) — pipeline clones via `git clone`. No upload size limit. Works for GitHub, GitLab, Bitbucket, self-hosted.
2. **Chunked upload** (new) — client splits ZIP into 200MB chunks, server reassembles, then runs extraction. Fallback for when Git URL is not available.

---

## 2. Git URL Path

### 2.1 Changes to `GitHubScanRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `github_url` | string | required | HTTPS Git URL (GitHub, GitLab, Bitbucket, self-hosted) |
| `use_git` | bool | `true` | Use `git clone` (always True; kept for compat) |
| `token` | string | null | Optional auth token (falls back to env vars) |
| `append_mode` | bool | `true` | Append results to existing architecture |
| `max_components_per_domain` | int | `10` | Max components per domain |
| `full_history` | bool | `false` | If `true`, clone with full history (no `--depth 1`). Required for repos > 6GB or when historical analysis is needed. |

### 2.2 Supported Hosts

- GitHub: bare token as username (`https://TOKEN@github.com/...`)
- GitLab: `oauth2:TOKEN` prefix
- Bitbucket: `USER:APP_PASSWORD`
- Self-hosted: `oauth2:TOKEN` fallback

Env var fallback order: explicit token → GITHUB_TOKEN / GITLAB_TOKEN / BITBUCKET_TOKEN → GIT_TOKEN.

### 2.3 Behavior

1. Client posts `GitHubScanRequest` to `/api/v1/code/extract-from-github`
2. Server validates URL format, runs `git clone --depth 1` (or full clone if `full_history=true`)
3. Clone completes synchronously (300s timeout)
4. Extraction runs async in background task
5. Client polls `GET /api/v1/code/scan/{task_id}`

---

## 3. Chunked Upload Protocol

### 3.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/code/upload/start` | Initiate upload session |
| `PUT` | `/api/v1/code/upload/chunk/{session_id}/{chunk_number}` | Upload a single chunk |
| `POST` | `/api/v1/code/upload/complete/{session_id}` | Finalize and start extraction |
| `DELETE` | `/api/v1/code/upload/session/{session_id}` | Cancel and cleanup |
| `GET` | `/api/v1/code/upload/session/{session_id}/status` | Get upload progress |

### 3.2 Start Session

**Request:**
```json
{
  "filename": "repo.zip",
  "total_chunks": 25,
  "expected_size_bytes": 5368709120,
  "expected_sha256": "abc123..."
}
```

All fields required except `expected_sha256`. If omitted, SHA256 validation is skipped (trust mode for internal/trusted networks).

**Response:**
```json
{
  "session_id": "uuid",
  "chunk_urls": [
    "/api/v1/code/upload/chunk/uuid/0",
    "/api/v1/code/upload/chunk/uuid/1",
    ...
  ],
  "expires_at": "2026-05-28T13:00:00Z"
}
```

### 3.3 Chunk Upload (PUT)

- URL: `/api/v1/code/upload/chunk/{session_id}/{chunk_number}`
- Body: raw binary bytes of chunk
- Max chunk size: **200MB** compressed
- Chunk numbers: `0` to `total_chunks - 1`
- Server writes chunk to `/tmp/kf-chunks/{session_id}/chunk_{chunk_number:06d}` after full receipt
- Server validates chunk size ≤ 200MB before writing
- **Out-of-order chunks allowed** — server tracks received chunks as an unordered set; order does not matter
- **Duplicate chunk upload rejected** — if chunk already received, returns `409 Conflict` (client should not retry the same chunk; only retry missing ones)
- **Expiry refreshed** — each successful chunk upload resets the session TTL to 1hr from now (prevents race condition where upload finishes just as session expires)

**Response (success):**
```json
{
  "received": true,
  "chunk_number": 5,
  "received_size_bytes": 209715200
}
```

**Response (duplicate chunk):**
```json
{
  "error": "chunk already received",
  "chunk_number": 5,
  "status": 409
}
```

### 3.4 Complete Session (POST)

**Request:** `POST /api/v1/code/upload/complete/{session_id}`

Server:
1. Verify all chunks received (compare received set size vs expected `total_chunks`)
2. Verify session not expired (if expired → 410 Gone, client must restart)
3. Reassemble chunks into `/tmp/kf-reassembled/{session_id}.zip` (requires up to 6GB free disk)
4. Compute SHA256 of reassembled file
5. Compare against `expected_sha256` from start
6. If mismatch → delete reassembled file, mark session failed, return 400
7. If valid → mark session `completed`, run `safe_extract_zip()` → `run_c4_extraction()` (same as direct upload)
8. Delete chunks directory immediately after successful reassembly

**Note on SHA256 pre-computation:** The client must compute the SHA256 hash of the complete ZIP before uploading chunks. For large files this takes measurable time (minutes on slow disks). The client should compute and send the hash in `/upload/start` to avoid wasting upload bandwidth on a corrupt file. If SHA256 is omitted in the start request, it defaults to `"unknown"` and validation is skipped (server trusts the client; suitable for trusted internal networks).

**Response:**
```json
{
  "task_id": "uuid",
  "status": "pending",
  "message": "ZIP reassembled and scan queued"
}
```

### 3.5 Cancel Session (DELETE)

**Request:** `DELETE /api/v1/code/upload/session/{session_id}`

Server: delete chunks directory, mark session expired.

**Response:**
```json
{
  "cancelled": true,
  "session_id": "uuid"
}
```

### 3.6 Session Status (GET)

**Response:**
```json
{
  "session_id": "uuid",
  "status": "uploading",
  "received_chunks": [0, 1, 2, 4, 5],
  "missing_chunks": [3],
  "total_chunks": 25,
  "expires_at": "2026-05-28T13:00:00Z"
}
```

Note: `received_chunks` is a set representation (order is irrelevant, not a list).

Status values: `uploading`, `completed`, `failed`, `expired`

---

## 4. Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Max chunk size (compressed) | 200 MB | Per individual chunk |
| Max total compressed bytes | 6 GB | Sum of all chunk sizes; enforced at `/complete` |
| Max total uncompressed size | 6 GB | Enforced by `safe_extract_zip()` per-member and total |
| Max total chunks per session | 30 | 30 × 200MB = 6GB max compressed |
| Session TTL | 1 hour from last chunk | Reset on each chunk upload; does not apply once session is `completed` |
| Session storage | `/tmp/kf-chunks/{session_id}/` | |

**Disk space note:** Reassembly requires free disk space equal to the total compressed size (up to 6GB). Ensure the `/tmp` partition has sufficient capacity.

---

## 5. Error Handling

| Error | HTTP | Action |
|-------|------|--------|
| Chunk > 200MB | 413 | Reject chunk, client retries |
| Duplicate chunk uploaded | 409 | Reject (chunk already received), client should only retry missing chunks |
| Out-of-order chunk | 200 | Accepted (server tracks set, order irrelevant) |
| Missing chunks on complete | 400 | Return `missing_chunks` list, client retries those specific chunks |
| SHA256 mismatch | 400 | Delete reassembled file, client must restart upload |
| Session expired (upload phase) | 410 | Client must restart upload |
| Session expired (during extraction) | N/A | Extraction continues regardless — expiry only blocks new chunk uploads, not in-progress work |
| Session not found | 404 | Client must restart upload |
| Server restart | N/A | Sessions lost, client retries from chunk 0 |

---

## 6. Cleanup

- **On complete**: chunks deleted, reassembled ZIP kept for duration of `safe_extract_zip()` validation only, then deleted. The extraction pipeline reads from the extracted directory (not the ZIP), so ZIP deletion does not affect extraction.
- **On cancel**: chunks deleted, session marked expired
- **On expire** (1hr TTL, "uploading" state only): background job deletes chunk directories + marks sessions expired. Sessions in `completed`, `failed` states are not affected.
- **Temp directories**: reuse existing `safe_extract_zip()` cleanup (extract dir deleted after extraction completes)

---

## 7. Integration

- Reassembly produces a valid ZIP at known path
- `safe_extract_zip()` validates the ZIP (same security checks as direct upload)
- `run_c4_extraction()` called identically to existing direct upload flow
- No changes to scan task tracking or result retrieval

---

## 8. Security

- Session IDs are UUID v4 (unguessable)
- Chunks written to disk with permissions 0o600 (owner only)
- `safe_extract_zip()` enforces: path traversal prevention, symlink rejection, uncompressed size limit (6GB)
- SHA256 verification prevents corrupted/malicious uploads from consuming extraction resources

---

## 9. Out of Scope

- Resumable uploads across server restarts (sessions are in-memory)
- Browser-based chunking UI (client responsibility)
- Direct streaming upload (multipart/x-mixed-replace)
- Repos > 6GB uncompressed (must use Git URL path)