# Bug Fixes Applied

## Bug 1: ✅ FIXED - DateTime parsing crash in git_contributor_analyzer.py

**Issue:** Line 152 used `.split('-')[0]` which returns only the year string, not the full date.

**Before:**
```python
commit_date = datetime.strptime(date_str.split('+')[0].split('-')[0].strip(), '%Y-%m-%d %H:%M:%S')
```

**After:**
```python
# Remove timezone first, then parse the full date string
clean_date = date_str.split('+')[0].strip()
commit_date = datetime.strptime(clean_date, '%Y-%m-%d %H:%M:%S')
```

**File:** `sources/Api/app/services/service_extraction/git_contributor_analyzer.py:152`

---

## Bug 2: ✅ FIXED - Async function in BackgroundTasks

**Issue:** `run_service_extraction()` was async with await statements, but `BackgroundTasks.add_task()` runs in a thread pool and can't properly execute async coroutines.

**Before:**
```python
async def run_service_extraction(task_id: str, ...):
    await broadcast_task_update(...)
    # ... more await calls
```

**After:**
```python
def run_service_extraction(task_id: str, ...):
    """Synchronous wrapper for BackgroundTasks."""
    import asyncio
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_run_service_extraction_async(...))
    finally:
        loop.close()

async def _run_service_extraction_async(task_id: str, ...):
    """Actual async implementation."""
    await broadcast_task_update(...)
    # ... async logic here
```

**File:** `sources/Api/app/endpoint/v1/routes/service_extraction.py:250-285`

---

## Bug 3: ✅ FIXED - BackgroundTasks default parameter

**Issue:** Using `background_tasks: BackgroundTasks = BackgroundTasks()` as default creates a single instance shared across requests.

**Before:**
```python
async def extract_from_zip(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),  # ❌ Wrong
):
```

**After:**
```python
async def extract_from_zip(
    background_tasks: BackgroundTasks,  # ✅ Injected by FastAPI
    file: UploadFile = File(...),
):
```

**File:** `sources/Api/app/endpoint/v1/routes/service_extraction.py:135-137`

**Note:** Moved `background_tasks` before `file` to avoid "non-default after default" error.

---

## Bug 4: ✅ FIXED - HTTP regex capture group mismatch

**Issue:** Patterns have different numbers of capture groups, but code unconditionally used `group(1)` for both URL and method, causing incorrect extraction.

**Patterns:**
- 1 group: `r'https?://([^/\s"\']+)'` → group(1) is URL, no method
- 2 groups: `r'axios\.(get|post)\([\'"]([^"\']+)[\'"]'` → group(1) is method, group(2) is URL

**Before:**
```python
for match in matches:
    url = match.group(1)  # ❌ Wrong for 2-group patterns (gets method)
    method = match.group(1) if len(match.groups()) > 1 else None  # ❌ Wrong for 1-group (gets URL)
```

**After:**
```python
for match in matches:
    num_groups = len(match.groups())
    
    if num_groups == 0:
        url = match.group(0)
        method = None
    elif num_groups == 1:
        url = match.group(1)  # ✅ Correct: URL
        method = None
    else:  # 2+ groups
        method = match.group(1)  # ✅ Correct: method
        url = match.group(2)     # ✅ Correct: URL
```

**File:** `sources/Api/app/services/service_extraction/service_relationship_discoverer.py:187-200`

---

## Testing

All fixes have been applied. To test:

```bash
# Copy fixed files to container
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
docker cp sources/Api/app/services/service_extraction/git_contributor_analyzer.py knowledgeforge-api:/app/app/services/service_extraction/
docker cp sources/Api/app/endpoint/v1/routes/service_extraction.py knowledgeforge-api:/app/app/endpoint/v1/routes/
docker cp sources/Api/app/services/service_extraction/service_relationship_discoverer.py knowledgeforge-api:/app/app/services/service_extraction/

# Restart
docker-compose restart api

# Test extraction
curl -X POST "http://localhost:8000/api/v1/services/extract-from-github" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/shuup/shuup", "use_git": true}'
```

Expected: Extraction should complete without crashes, git dates parsed correctly, and background tasks execute properly.

