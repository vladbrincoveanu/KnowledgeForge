# Large Repo Extraction Fix — 2026-05-30

## Problem

Extraction on large multi-repo zips (CMS = 39 child repos, 10GB+) stalls after Level 1. Root causes:

1. `KF_MAX_FILES_PER_GLOB=5000` is shared across all `limited_rglob` calls in a single extraction. With 20+ calls in `metadata_detector`, `system_detector`, and `dependency_detector`, the budget is exhausted before component extraction.
2. `metadata_detector._scan()` uses unbounded `glob('**/*.json')` — no limit at all.
3. `run_c4_extraction` only catches `ConnectionError` and `RuntimeError` — any other exception (LLM, tree-sitter, etc.) kills the background task silently, no error in `scan_tasks`, temp dir never cleaned.
4. The `finally:` block in `run_c4_extraction` only cleans on `ConnectionError`/`RuntimeError`, not on the generic `Exception` case.

## Fix

### 1. Raise default `max_files` to 50k

`app/utils/fs_utils.py`:
```
MAX_FILES_PER_GLOB = 50_000  # was 5_000
```

### 2. Per-call budgets in `metadata_detector._scan()`

Replace the 20+ individual `limited_rglob` calls with per-call budgets so each glob pattern gets its own limit instead of sharing one.

`app/services/c4/context/metadata_detector.py` — `_scan()` method:
- `source_globs` loop: `max_files=2000` per pattern
- `glob('**/*.json')`: replaced with `limited_rglob(..., pattern='*.json', max_files=1000)`

### 3. Replace unbounded `glob` in metadata_detector

`metadata_detector.py` line 637:
```python
# before
for json_file in self.repo_path.glob('**/*.json'):

# after
for json_file in limited_rglob(self.repo_path, '*.json', max_files=1000):
```

### 4. Broad exception handling in `run_c4_extraction`

```python
except Exception as e:
    logger.error(f"C4 extraction failed for task {task_id}: {e}", exc_info=True)
    task = scan_tasks.get(task_id)
    if task:
        task['status'] = 'failed'
        task['message'] = f'Extraction failed: {str(e)}'
        task.setdefault('errors', []).append(str(e))
```

### 5. Guaranteed temp dir cleanup

Move cleanup into `finally:` block so it runs regardless of how `run_c4_extraction` exits.

## Files Changed

- `app/utils/fs_utils.py` — raise default limit
- `app/services/c4/context/metadata_detector.py` — per-call budgets, replace unbounded glob
- `app/endpoint/v1/routes/code_extraction.py` — broad exception, guaranteed cleanup

## Testing

1. Start fresh: `make down && make up`
2. Upload CMS zip via chunked upload
3. `POST /upload/complete` → 202 + `UploadCompleteResponse`
4. Wait for extraction (may take 5-10 min for 39 repos)
5. Verify: JSON file in `c4_extractions/`, Neo4j has nodes, temp dir gone
6. `GET /api/v1/code/scan/{task_id}/status` → `completed`
