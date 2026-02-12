# KnowledgeForge — Claude Instructions

## Task Planning Files

All task plans, sprint docs, feature status dumps, and improvement tracking files live in:

```
docs/plans/
```

**Always put new task/planning MD files there, never at the repo root.**

Current files:
- `docs/plans/REFACTORING_MASTER_PLAN.md` — 28 refactoring tasks + 14 context improvements
- `docs/plans/ITIL_CMDB_SERVICE_CATALOG_PLAN.md` — ITIL CMDB field coverage plan
- `docs/plans/context_imrpovements.md` — C4 context field specification (v1.0)
- `docs/plans/FEATURE_CODEFORGE_STATUS.md` — Final status dump for feature/CODEFORGE

Architecture docs live in `docs/architecture/`.

---

## Scope Boundary

We own the **Context Level** only. Do NOT modify `sources/Api/app/services/c4/containers/` — that is owned by a separate squad.

## Test Commands

```bash
# Backend
docker compose exec -T api python -m pytest tests/ -v

# Frontend
cd sources/UI && npx vitest run

# Quick check
docker compose exec -T api python -m pytest tests/ -q 2>&1 | tail -5
```

## Current Status

**251/251 backend tests passing. 84/84 frontend tests passing.**
