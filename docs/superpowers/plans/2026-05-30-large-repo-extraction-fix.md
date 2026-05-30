# Large Repo Extraction Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraction on large multi-repo zips (39 child repos, 10GB+) completes fully instead of stalling after Level 1.

**Architecture:** Three targeted fixes: (1) raise the global file-traversal cap, (2) replace one unbounded glob with a bounded rglob, (3) broaden exception handling and guarantee temp cleanup so background tasks fail visibly.

**Tech Stack:** Python3.11, FastAPI background tasks, `pathlib.Path.rglob`

---

## Files Changed

| File | Change |
|------|--------|
| `sources/Api/app/utils/fs_utils.py` | Raise `MAX_FILES_PER_GLOB` default 5000 → 50000 |
| `sources/Api/app/services/c4/context/metadata_detector.py` | Replace unbounded `glob('**/*.json')` with `limited_rglob(..., '*.json', max_files=1000)` |
| `sources/Api/app/endpoint/v1/routes/code_extraction.py` | `except Exception` instead of `except (ConnectionError, RuntimeError)` + move cleanup to `finally:` |

---

## Task 1: Raise global `MAX_FILES_PER_GLOB`

**Files:** `sources/Api/app/utils/fs_utils.py:12`

- [ ] **Step 1: Edit `fs_utils.py`**

```python
MAX_FILES_PER_GLOB = int(os.getenv("KF_MAX_FILES_PER_GLOB", os.getenv("MAX_FILES_PER_GLOB", "50000")))
```

- [ ] **Step 2: Commit**

```bash
git add sources/Api/app/utils/fs_utils.py
git commit -m "fix: raise MAX_FILES_PER_GLOB from 5k to 50k for large repos"
```

---

## Task 2: Replace unbounded `glob` with `limited_rglob`

**Files:** `sources/Api/app/services/c4/context/metadata_detector.py:637`

- [ ] **Step 1: Read the surrounding context**

Lines 636-642:
```python
        # Scan *.json config files one level deep (appsettings.*.json pattern)
        for json_file in self.repo_path.glob('**/*.json'):
            if _should_skip(json_file) or json_file.stat().st_size > 50_000:
                continue
            if any(k in json_file.name.lower() for k in ('appsettings', 'config', 'settings')):
                _scan_file(json_file)
```

- [ ] **Step 2: Edit `metadata_detector.py` line 637**

Replace:
```python
        for json_file in self.repo_path.glob('**/*.json'):
```
With:
```python
        for json_file in limited_rglob(self.repo_path, '*.json', max_files=1000):
```

- [ ] **Step 3: Commit**

```bash
git add sources/Api/app/services/c4/context/metadata_detector.py
git commit -m "fix: replace unbounded glob with limited_rglob in metadata_detector"
```

---

## Task 3: Broad exception handling + guaranteed cleanup

**Files:** `sources/Api/app/endpoint/v1/routes/code_extraction.py:1280-1347`

- [ ] **Step 1: Read the current `run_c4_extraction` exception handling**

Lines1280-1347 — current structure:
```python
    try:
        task['status'] = 'scanning'
        task['progress'] = 0.1
        task['message'] = 'Cloning repository'
        llm = get_llm_manager()
        extractor = C4ArchitectureExtractor(repo_path=repo_path, llm_manager=llm)
        task['progress'] = 0.2
        task['message'] = 'Analysing architecture'
        c4_architecture = await asyncio.to_thread(
            extractor.extract,
            max_components_per_domain=max_components,
            task_id=task_id,
            repo_url=task.get('github_url', ''),
        )
        task['progress'] = 0.9
        task['message'] = f'Extracted {len(c4_architecture["containers"])} containers...'
        task['containers_count'] = len(c4_architecture['containers'])
        task['components_count'] = len(c4_architecture['components'])
        task['external_deps_count'] = len(c4_architecture['system_context'].get('external_dependencies', []))
        task['c4_architecture'] = c4_architecture
        _save_c4_to_json(task_id, c4_architecture)
        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'C4 extraction completed successfully'
        task['completed_at'] = datetime.now()
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
            if 'temp_dir' in task:
                try:
                    shutil.rmtree(task['temp_dir'])
                except (ConnectionError, RuntimeError) as cleanup_err:
                    logger.warning(f"Failed to cleanup temp directory on failure: {cleanup_err}")
        else:
            logger.error(f"Task {task_id} disappeared during error handling")
```

- [ ] **Step 2: Replace exception handling and add `finally:`**

Replace the entire `try/except/finally` block with:

```python
    try:
        task['status'] = 'scanning'
        task['progress'] = 0.1
        task['message'] = 'Cloning repository'

        llm = get_llm_manager()
        extractor = C4ArchitectureExtractor(repo_path=repo_path, llm_manager=llm)

        task['progress'] = 0.2
        task['message'] = 'Analysing architecture'
        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")

        c4_architecture = await asyncio.to_thread(
            extractor.extract,
            max_components_per_domain=max_components,
            task_id=task_id,
            repo_url=task.get('github_url', ''),
        )

        task['progress'] = 0.9
        task['message'] = f'Extracted {len(c4_architecture["containers"])} containers, {len(c4_architecture["components"])} components'
        task['containers_count'] = len(c4_architecture['containers'])
        task['components_count'] = len(c4_architecture['components'])
        task['external_deps_count'] = len(c4_architecture['system_context'].get('external_dependencies', []))
        task['c4_architecture'] = c4_architecture

        _save_c4_to_json(task_id, c4_architecture)

        logger.info(f"{task['message']} (progress: {int(task['progress'] * 100)}%)")

        task['progress'] = 1.0
        task['status'] = 'completed'
        task['message'] = 'C4 extraction completed successfully'
        task['completed_at'] = datetime.now()

        logger.info(f"C4 extraction completed for task {task_id}")

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

    finally:
        if 'temp_dir' in task:
            try:
                shutil.rmtree(task['temp_dir'])
            except (ConnectionError, RuntimeError, OSError) as cleanup_err:
                logger.warning(f"Failed to cleanup temp directory: {cleanup_err}")
```

- [ ] **Step 3: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py
git commit -m "fix: broad exception handling + guaranteed temp cleanup in run_c4_extraction"
```

---

## Task4: Smoke test with CMS zip

**Files:** None changed — verification only

- [ ] **Step 1: Rebuild API image**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
docker compose build api
```

- [ ] **Step 2: Start services**

```bash
docker compose up -d
sleep 10
docker compose ps
```

- [ ] **Step 3: Copy CMS zip into container**

```bash
docker cp ~/Downloads/cms.eventsourcing.zip knowledgeforge-api:/tmp/cms.zip
```

- [ ] **Step 4: Run full upload + complete flow**

```python
# In container:
import requests, hashlib, os

h = hashlib.sha256()
with open('/tmp/cms.zip', 'rb') as f:
    while chunk := f.read(8192): h.update(chunk)
sha = h.hexdigest()
size = os.path.getsize('/tmp/cms.zip')

resp = requests.post('http://localhost:8000/api/v1/code/upload/start',
    json={'filename': 'cms.eventsourcing.zip', 'total_chunks': 29,
          'expected_size_bytes': size, 'expected_sha256': sha}, timeout=30)
session_id = resp.json()['session_id']

# Recreate chunks
os.makedirs('/app/data/chunks', exist_ok=True)
with open('/tmp/cms.zip', 'rb') as f:
    i = 0
    while True:
        data = f.read(150*1024*1024)
        if not data: break
        with open(f'/app/data/chunks/chunk_{i:02d}', 'wb') as out: out.write(data)
        i += 1

# Upload chunks
for i in range(i):
    with open(f'/app/data/chunks/chunk_{i:02d}', 'rb') as f:
        data = f.read()
    requests.put(f'http://localhost:8000/api/v1/code/upload/chunk/{session_id}/{i}',
        data=data, headers={'Content-Type': 'application/octet-stream'}, timeout=120)

# Complete
resp = requests.post(f'http://localhost:8000/api/v1/code/upload/complete/{session_id}', timeout=600)
print(f'Complete: {resp.status_code} — {resp.text[:200]}')
task_id = resp.json()['task_id']
print(f'Task ID: {task_id}')
```

- [ ] **Step 5: Monitor extraction**

```python
import time
for _ in range(120):
    resp = requests.get(f'http://localhost:8000/api/v1/code/scan/{task_id}/status', timeout=30)
    if resp.status_code == 200:
        d = resp.json()
        print(f"{d['status']} | {d['progress']:.0%} | {d['message']}")
        if d['status'] in ('completed', 'failed'):
            break
    time.sleep(15)
```

- [ ] **Step 6: Verify results**

```bash
# Check JSON landed
docker exec knowledgeforge-api ls -lt /app/sources/data/c4_extractions/ | head -3

# Check Neo4j has nodes
docker exec knowledgeforge-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" "MATCH (n) RETURN count(n)"

# Check temp dir cleaned
docker exec knowledgeforge-api ls /tmp/ | grep <task_id>
# Should return empty
```

---

## Verification Checklist

- [ ] `POST /upload/start` → 201 + session_id
- [ ] All 29 `PUT /upload/chunk` → 200
- [ ] `POST /upload/complete` → 202 + `UploadCompleteResponse` (not `UploadCancelResponse`)
- [ ] `GET /scan/{task_id}/status` → `completed` (not `failed`)
- [ ] JSON file in `c4_extractions/` with non-empty systems/containers
- [ ] Neo4j nodes exist
- [ ] Temp dir `/tmp/repo_{task_id}_*` is gone
- [ ] No `limited_rglob: reached max_files` warnings in logs for CMS zip
