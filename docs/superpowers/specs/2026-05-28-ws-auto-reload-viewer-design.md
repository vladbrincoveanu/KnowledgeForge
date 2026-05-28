# WS Auto-Reload: Fix Disconnected Extraction Entry Points

**Date:** 2026-05-28
**Type:** Bug Fix (Frontend + Backend)

---

## Problem

Two separate extraction entry points in the app:

1. **`/workspace`** → `FileUploader` — handles GitHub URLs and local folder ZIP uploads
2. **`/code-architecture`** → `CodeArchitectureViewer` — displays C4 diagrams, has its own GitHub URL / local path inputs

When a user uploads a ZIP via `FileUploader`:
1. Zip → `POST /api/v1/code/upload-repo` → extraction runs async
2. On completion → results written to DB
3. `CodeArchitectureViewer` on `/code-architecture` never finds out — it only loads architecture on mount via `useEffect` + `getArchitecture()`

Result: ZIP upload appears to succeed in the repo list UI, but the architecture viewer still shows old/demo data.

---

## Design Decisions (Grill-Me'd)

### D1: Broadcast location — inside `run_c4_extraction` or endpoint?
**Decision:** `run_c4_extraction` is shared by all entry points (GitHub URL, zip upload, local scan, batch). Putting broadcast there ensures **all** extractions trigger the event, not just one endpoint.

### D2: Event payload — lightweight trigger vs full results over WS?
**Decision:** Two events:
- `extraction_completed` — `{type, task_id, timestamp}` — lightweight trigger only
- `extraction_complete` (existing) — `{type, task_id, status, results, timestamp}` — full results (kept as-is)

Clients use `extraction_completed` to know to call `getArchitecture()`. This avoids streaming large JSON over WS when clients can poll for it.

### D3: Reload timing — immediate or only when viewer is visible?
**Decision:** Immediate reload. WS event fires → viewer calls `getArchitecture()` on next tick. No visibility tracking or debounce (YAGNI — add only if proven needed).

### D4: Failed extractions — broadcast on failure too?
**Decision:** Yes. `extraction_failed` event with `{type, task_id, message, timestamp}` lets viewer show error state without corrupting displayed data.

---

## Architecture

### Backend (`sources/Api/app/endpoint/v1/routes/code_extraction.py`)

In `run_c4_extraction`, after `task['status'] = 'completed'`:

```python
from app.endpoint.v1.routes.websocket import broadcast_task_update

# In success block, after task['status'] = 'completed':
await broadcast_task_update(
    task_id,
    status="completed",
    message=task["message"],
    progress=1.0,
    extra={"containers_count": task.get("containers_count"), "components_count": task.get("components_count")},
)

# In failure block:
task["status"] = "failed"
await broadcast_task_update(
    task_id,
    status="failed",
    message=task["message"],
    extra={"error": str(e)},
)
```

Note: `broadcast_task_update` is already wired to `manager.broadcast` → all WS clients receive it.

### Frontend (`sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`)

Add WS subscription in existing `useEffect` alongside the mount-load:

```typescript
useEffect(() => {
  const handler = (data: any) => {
    // Reload on any extraction completion (from any entry point)
    if (data?.type === "task_update" && data?.status === "completed") {
      loadArchitecture();
    }
  };
  wsService.on("message", handler);
  return () => wsService.off("message", handler);
}, [loadArchitecture]);
```

Also handle failure:

```typescript
if (data?.type === "task_update" && data?.status === "failed") {
  showNotification(`Extraction failed: ${data?.message}`, "error");
}
```

**Key detail:** `loadArchitecture` must be stable (useCallback). Currently it's defined inside the component's `useEffect` at line 1504. Extract it as `useCallback` at top level so the WS subscription's `useEffect` can depend on it.

### WS Message Format

`broadcast_task_update` sends:
```json
{
  "type": "task_update",
  "task_id": "uuid",
  "status": "completed" | "failed",
  "message": "C4 extraction completed successfully",
  "progress": 1.0,
  "containers_count": 12,
  "components_count": 47,
  "timestamp": "ISO8601"
}
```

---

## Files Changed

| File | Change |
|------|--------|
| `sources/Api/app/endpoint/v1/routes/code_extraction.py` | Import and call `broadcast_task_update` in `run_c4_extraction` on both success and failure |
| `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx` | Extract `loadArchitecture` to stable `useCallback`; add WS subscription for `task_update` events; handle failure display |

---

## Tests

### Backend
- `test_run_c4_extraction_broadcasts_on_completion` — mocks `broadcast_task_update`, runs extraction, asserts called with status=completed
- `test_run_c4_extraction_broadcasts_on_failure` — mocks failure, asserts `broadcast_task_update` called with status=failed

### Frontend
- Existing WS tests in `CodeArchitectureViewer.test.tsx` extended — assert `loadArchitecture` called when WS message with `type: "task_update", status: "completed"` received
- New test: assert notification shown when `type: "task_update", status: "failed"` received

---

## Spec Self-Review

- [x] No TBD/TODO placeholders — all decisions explicit
- [x] Internal consistency — backend broadcasts, frontend subscribes, message format matched
- [x] Scope: one focused bug fix — not expanding to "improve all WS events"
- [x] Ambiguity: payload fields explicit, timing ("immediate") stated
- [x] Fail path: `loadArchitecture` wrapped in try/catch (already exists at line 1504-1515), failures surface as error state (already handled)
