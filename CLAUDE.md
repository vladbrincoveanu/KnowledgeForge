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

## Workflows

### Creating/Modifying API Endpoints

When creating new API endpoints:

1. First plan the new endpoint changes, including new/updated methods, paths and request payloads
2. Confirm proposed changes with user
3. Implement the endpoint
4. Add/update endpoint in the .http file, including documenting endpoint and payloads
5. Test the .http file using: `docker run --rm -i -t -v $PWD:/workdir jetbrains/intellij-http-client <http_file_name>`

## Code Style

- General:
  - Prefer writing clear code and use inline comments sparingly
- C#:
  - 4-space indent
  - `PascalCase` for classes/methods
  - `_camelCase` for private fields
  - `camelCase` for local variables, parameters
  - Prefer primary constructors where possible
  - Use auto-properties, and `field` if necessary
  - Write XML comments on all classes, methods, properties and fields
  - Tests:
    - `<ClassName>Tests` for test class
    - `<MethodName>_<Conditions>_<AssertedOutcome>` for test methods (never `Async` suffix)
    - Arrange, Act, Assert pattern (comment each section in method)
- TypeScript/JavaScript/CSS:
  - 2-space indent
  - Document all methods, types and interfaces with JSDoc comments
  - Keep `*.test.ts` files in same directory as corresponding `*.ts` file
- Commits:
  - Use Conventional Commit format
  - **Commit Types:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
  - **Scopes:** `web`, `api`, `docker`

## Documentation Principles

- Domain-Specific Jargon
- Architectural Decisions and Structure
- Keep It Concise
- Treat It Like a Living Document

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
