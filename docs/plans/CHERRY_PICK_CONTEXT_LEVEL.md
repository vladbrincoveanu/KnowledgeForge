# Cherry-Pick Plan: Context Level to Main Branch

## Objective
Bring essential context-level code from `feature/CODEFORGE` to `main` while keeping `main` clean.

## Current State

| Branch | Context Files |
|--------|---------------|
| **main** | `__init__.py`, `context_manager.py`, `system_detector.py`, `dependency_detector.py`, `metadata_detector.py` |
| **feature/CODEFORGE** | + 8 new files (canonical_models, harvesters, merge_engine, etc.) |

---

## Cherry-Pick Order (Dependencies First)

### Step 1: Foundation Layer
| Commit | Hash | Files Added |
|--------|------|--------------|
| Canonical models + merge foundation | `df411f95` | `canonical_models.py`, `feature_flags.py`, `harvesters.py`, `merge_engine.py`, `precedence.py`, `stores.py` |

### Step 2: Service Layer
| Commit | Hash | Files Added |
|--------|------|--------------|
| Level1 Context Review Endpoints | `9b2788b6` | `level1_context_service.py`, `context.py` route |
| WPS Quality Gate + Rollout | `9a564992` | `quality_gate.py` |

### Step 3: Integration
| Commit | Hash | Files Added |
|--------|------|--------------|
| Implement-plan tasks 3.x/4.x | `6e567e5f` | (duplicates - skip) |

---

## Commands to Execute

```bash
# 1. Ensure on main branch and clean
git checkout main
git pull origin main
git status  # Should be clean

# 2. Cherry-pick in order (newest first to handle dependencies)
git cherry-pick df411f95
git cherry-pick 9b2788b6
git cherry-pick 9a564992

# 3. Verify tests pass
docker compose exec -T api python -m pytest tests/unit/services/c4/context/ -v
```

---

## Files That Will Be Added

```
sources/Api/app/services/c4/context/
├── __init__.py          # Updated (exports)
├── canonical_models.py  # NEW - Canonical entity definitions
├── feature_flags.py     # NEW - Feature flag system
├── harvesters.py        # NEW - Repository/service harvesters
├── level1_context_service.py  # NEW - REST endpoints
├── merge_engine.py      # NEW - Context merge logic
├── precedence.py        # NEW - Field precedence
├── quality_gate.py      # NEW - Quality gates
└── stores.py            # NEW - Storage implementations
```

---

## What to SKIP (Not Context Level)

These are NOT part of context-level extraction and should NOT be cherry-picked:

- **Code Extraction** (`code_extraction/`) - Container/Component level
- **Container Detection** (`c4/containers/`) - Container level
- **Frontend UI** (`sources/UI/`)
- **Architecture docs** (`docs/architecture/`)

---

## Post-Cherry-Pick Checklist

- [ ] Run backend tests: `docker compose exec -T api python -m pytest tests/unit/services/c4/context/ -v`
- [ ] Verify imports work: `docker compose exec -T api python -c "from app.services.c4.context import *"`
- [ ] Push to main: `git push origin main`
- [ ] Update CLAUDE.md if needed

---

## Rollback Plan (if needed)

```bash
# Undo last cherry-pick
git reset --hard HEAD~1

# Or undo all
git reset --hard origin/main
```
