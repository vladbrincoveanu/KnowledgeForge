# Extraction Flexibility Enhancement Plan

## Problem Statement

The current extraction system is too strict and misses many valid containers:
- **Python libraries** without `__main__.py` are ignored
- **Monorepo patterns** like `projects/`, `libs/`, `packages/` are not detected
- **Context purpose** is shallow (just README parsing)
- **Actor detection** is minimal (only doc headings)

### Example: dagster-slurm

| Directory | Current Detection | Should Be |
|----------|------------------|-----------|
| `projects/dagster-slurm/dagster_slurm/` | NOT detected (Python library) | Container (Python Library) |
| `projects/dagster-slurm/dagster_slurm_test/` | NOT detected (tests) | Skip |
| `projects/dagster-slurm/examples/` | NOT detected (examples) | Container (Example) |
| `services/slurm/` | Detected (has Dockerfile) | Container (Docker) |
| Root `pyproject.toml` | NOT detected (root) | System level |

---

## Root Causes

### 1. `is_deployable_service()` is too strict (`utils.py`)

```python
# Current: Requires __main__.py for Python
if pyproject.exists() or requirements.exists():
    if _has_python_entrypoint(directory):  # Needs __main__.py
        return True
    return False  # Library without __main__.py = NOT deployable
```

### 2. Directory pruning misses monorepo patterns

```python
# Current excluded dirs (from structure_detector.py):
excluded_dirs = {
    'test', 'tests', '__tests__', 'docs', ...
}
# Missing: 'projects', 'libs', 'packages', 'examples'
```

### 3. LLM is only used as fallback, not primary

- `context_manager.py`: LLM only for description generation (fallback)
- `system_detector.py`: README parsing is primary, LLM is secondary
- No LLM for **container type inference**

---

## Implementation Plan

### Phase 1: Quick Wins - Detection Pattern Expansion

**Goal**: Detect more directories without changing detection logic fundamentally.

#### 1.1 Add monorepo directory patterns to `StructureDetector`

**File**: `sources/Api/app/services/c4/containers/structure_detector.py`

```python
# Add to excluded_dirs or modify is_deployable_service():
common_service_dirs = {'projects', 'services', 'libs', 'packages', 'components', 'bases', 'examples'}
```

#### 1.2 Add `PythonLibraryDetector`

**File**: `sources/Api/app/services/c4/containers/python_library_detector.py` (new)

Detect directories with:
- `__init__.py` (pure Python indicator)
- `pyproject.toml` or `setup.py` or `setup.cfg`
- NOT having `__main__.py` (distinguishes library from app)

**Container type**: `Python Library`

```python
def detect_libraries(repo_path: Path) -> list[Container]:
    """Find Python packages/libraries that are not applications."""
    libraries = []
    for init_file in repo_path.rglob("__init__.py"):
        dir_path = init_file.parent
        if dir_path == repo_path:  # Skip root
            continue
        if _is_library(dir_path) and not _is_application(dir_path):
            libraries.append(_create_library_container(dir_path))
    return libraries
```

#### 1.3 Register `PythonLibraryDetector` in `ContainerManager`

**File**: `sources/Api/app/services/c4/containers/container_manager.py`

```python
from app.services.c4.containers.python_library_detector import PythonLibraryDetector

# In detect():
containers.extend(PythonLibraryDetector(repo_path).detect())
```

---

### Phase 2: LLM-Enhanced Container Classification

**Goal**: Use LLM to intelligently determine container type and significance.

#### 2.1 Create LLM Container Classifier

**File**: `sources/Api/app/services/c4/containers/llm_container_classifier.py` (new)

**Prompt**:
```
Analyze this directory and determine if it's a meaningful C4 container.

Directory: {rel_path}
Structure: {file_tree}
Key modules: {module_names}
Dependencies: {deps}
README excerpt: {readme[:500]}

Return JSON:
{
  "is_container": true/false,
  "container_type": "library|service|tool|example|infrastructure|unknown",
  "technology": "Python/FastAPI",
  "protocol": "HTTP|gRPC|messaging|internal|CLI",
  "significance": 0.0-1.0,
  "reasoning": "brief explanation"
}
```

#### 2.2 Integrate into extraction pipeline

**Option A**: Use as **pre-filter** - LLM decides what's a container before heuristic analysis
**Option B**: Use as **post-filter** - Heuristics find candidates, LLM validates and classifies

**Recommended**: Option B (hybrid) - faster, fallback on LLM failures

#### 2.3 Add config options

**File**: `sources/Api/app/utils/config.py`

```python
"extraction": {
    ...
    "detection": {
        "include_libraries": True,        # Detect Python packages
        "include_examples": False,        # Include example projects
        "min_significance": 0.5,         # LLM-assessed significance threshold
    },
    "llm_detection": {
        "enabled": True,
        "fallback_to_heuristic": True,   # Use heuristics if LLM fails
    }
}
```

---

### Phase 3: LLM-Enhanced Context Extraction

**Goal**: Better system purpose and actor detection.

#### 3.1 LLM-Primary Purpose Generation

**File**: `sources/Api/app/services/c4/context/system_detector.py`

**Current flow**:
1. Parse README → extract purpose (primary)
2. LLM generate description (fallback)

**New flow**:
1. **LLM analyzes** README + code structure → generate purpose (primary)
2. Validate with heuristics (fallback)

**New prompt**:
```
Generate a C4 system purpose statement for this codebase.

System name: {name}
README: {readme}
Language distribution: {languages}
Key components: {components}

Purpose (2-3 sentences):
```

#### 3.2 Actor Detection from Code Patterns

**File**: `sources/Api/app/services/c4/context/actor_detector.py` (new)

Detect actors from:
- Auth decorators (`@login_required`, `OAuth`, `JWT`)
- API endpoint patterns (`/api/users`, `/admin/`)
- CLI entrypoints (`argparse`, `typer`, `click`)
- User-facing vs internal indicators

**LLM prompt**:
```
Identify actors in this codebase.

Auth patterns found: {auth_patterns}
API endpoints: {endpoints}
CLI tools: {cli}
User-facing surfaces: {ui_components}

Actors (list with description):
- Name: role, brief description
```

---

### Phase 4: Quality Improvements

#### 4.1 Better Container Descriptions

**File**: `sources/Api/app/services/c4/containers/utils.py`

Replace generic descriptions with LLM-generated:
```python
def generate_container_description(container_path: Path) -> str:
    """Generate description from README + code analysis."""
    # Use LLM with context: README, key modules, public API
```

#### 4.2 Reduce False Positive External Dependencies

**Current**: URL pattern matching on ALL URLs in README
**Problem**: Badge URLs, CI URLs, irrelevant links create noise

**Fix**: LLM validates if URL represents a meaningful integration:
```
Does this URL represent a real external dependency/integration?
URL: {url}
Context: {where_found}
```

#### 4.3 Relationship Inference

Use LLM to infer relationships from:
- Environment variable names (`REDIS_URL` → uses Redis)
- Image names (`postgres:15` → uses PostgreSQL)
- Import patterns (`from dagster import` → uses Dagster)

---

## Files to Modify

| File | Change |
|------|--------|
| `containers/structure_detector.py` | Add `projects/` pattern detection |
| `containers/container_manager.py` | Register new detectors |
| `containers/utils.py` | Expand `is_deployable_service()` |
| `context/system_detector.py` | LLM-primary purpose extraction |
| `utils/config.py` | Add detection config options |

## Files to Create

| File | Purpose |
|------|---------|
| `containers/python_library_detector.py` | Detect Python packages |
| `containers/llm_container_classifier.py` | LLM-based container classification |
| `context/actor_detector.py` | LLM-based actor detection |

---

## Testing Plan

1. **dagster-slurm extraction** - Should detect:
   - `dagster_slurm` (Python library)
   - `dagster_slurm_example` (example project, optional)
   - `services/slurm` (Docker cluster)

2. **OmniPay extraction** - Should still pass (regression test)

3. **Edge cases**:
   - Pure library repos (no services)
   - Monorepos with mixed libs/services
   - Single-file scripts (should NOT be containers)

---

## Priority Order

1. **Phase 1.1-1.3** - Quick detection fixes (low effort, high impact)
2. **Phase 2.1-2.2** - LLM classification (medium effort)
3. **Phase 3.1** - Better purpose extraction (medium effort)
4. **Phase 2.3** - Config options (low effort)
5. **Phase 3.2** - Actor detection (higher effort, lower priority)
6. **Phase 4** - Quality improvements (ongoing)

---

## Success Metrics

- dagster-slurm: 1 container → 2-3 containers detected
- OmniPay: All 48 tests still passing
- External dependencies: Reduce noise (no badge URLs)
- Purpose descriptions: Meaningful vs generic
