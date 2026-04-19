# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

KnowledgeForge is a C4 architecture extraction engine that analyzes codebases and produces structured C4-level graphs (Context, Container, Component, Code). It transforms messy repositories into graph insights stored in Neo4j.

**Stack:** FastAPI (Backend) | React/TypeScript (Frontend) | Neo4j (Graph) | PostgreSQL (Metadata) | Docker

---

## Critical Commands

**Always run after implementing changes:**

```bash
make quick-check    # Fast restart + tests (1-2 min) — use for most changes
make full-check     # Complete rebuild + tests (5-10 min) — infrastructure/Docker changes
make ci             # CI/CD pipeline simulation — run before merging
```

**E2E Tests:**
- `docker compose exec api python -m pytest tests/ -v` — all tests
- `docker compose exec api python -m pytest tests/e2e/test_omnipay_extraction.py -v` — OmniPay demo tests
- `docker compose exec api python tests/test_pipeline.py` — pipeline integration

---

## Architecture

### Workspace Separation (The "Iron Curtain")

```
sources/Api/app/services/c4/context/     # Context-level extraction — OUR WORKSPACE
sources/Api/app/services/c4/containers/   # Container-level extraction — OTHER SQUAD'S WORKSPACE
```

**Do NOT modify `containers/`** unless explicitly coordinating with the other developer.

### Extraction Pipeline

```
GitHub URL → ServiceDiscovery → Language/API/Deployment Detection
    → ServiceEnhancers (8 phases: compliance, docs, comms, auth, etc.)
    → Neo4j (graph) + PostgreSQL (metadata)
```

Key files:
- `sources/Api/app/services/service_extraction/service_enhancers.py` — Enhancement chain
- `sources/Api/app/services/c4/context/context_manager.py` — Context extraction orchestrator
- `sources/Api/app/services/c4/containers/container_manager.py` — Container extraction

### Service Data Format

Each extracted service has **5 primary fields**:
1. `domain` — Business domain (e.g., "ai", "docs", "api")
2. `owner` — From git history (top contributor), never "Unassigned" when git exists
3. `status` — "Active-Dev", "Maintenance-Only", "Deprecated / Frozen"
4. `tier` — "Tier 1", "Tier 2", "Tier 3", "Unknown"
5. `data_class` — "PII", "Credit-Card", "Internal", "Public", "Unknown"

---

## Key Conventions

### Error Handling
- **Never** use bare `except Exception:` (except for 3rd-party LLM calls)
- Use typed exceptions from `app.domain.exceptions.py`

### Pydantic V2
- Strict typing; enums use `.value` for membership checks
- Use `Field()` for validation constraints
- Use `validate_by_name` (NOT `allow_population_by_field_name`)

### Git History
- `full_history=True` required for accurate owner detection in `github_downloader.py`

### ServiceStatus Values
Canonical values: `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` — NOT old strings like "Active-Dev"

### Endpoints
Extract from Helm `values.yaml`, Ingress, and README docs

### Zip Extraction
Always use `safe_extract_zip()` to block path traversal

### Storage
- **PostgreSQL:** metadata, configuration, task tracking
- **Neo4j:** entity nodes, relationship edges, graph operations
- **JSON files:** extraction results at `sources/data/c4_extractions/{task_id}.json`

---

## Python Standards

- Python 3.11, FastAPI, Pydantic V2
- Use **Black** (88-char line length), **Ruff** for linting, **mypy** for type checking
- Google-style docstrings for all public functions
- Use `pathlib` instead of `os.path`
- Use f-strings over `.format()` or `%` formatting
- **Never create empty folders or placeholder files** without explicit permission

---

## React/Frontend Standards

### Core Principles
- Functional components with hooks exclusively
- `React.memo()` for expensive components
- Proper error boundaries for graceful error handling
- `useCallback`/`useMemo` for performance-critical functions
- Never create empty folders or placeholder files without explicit permission

### Visualization
- ReactFlow zoom range: `0.1` to `2.0`
- Key labels must be human-readable (Tier, Status, Compliance, etc.)
- Tooltip CSS: `position: fixed` (for viewport-relative positioning)

### Accessibility
- Semantic HTML elements (button, nav, main, aside)
- Proper ARIA labels and roles
- Keyboard navigation for all interactive elements
- WCAG AA color contrast compliance
- `cursor-pointer` on all interactive elements

### Code Quality (run after every UI change)
```bash
cd sources/UI
npm run fix-all      # prettier + eslint fixes
npm run check-all    # type-check + lint + format check
npm run test         # all tests (mandatory before declaring done)
```

---

## Testing

### Backend
```bash
docker compose exec api python -m pytest tests/ -v
docker compose exec api python tests/test_pipeline.py
```

### Frontend
```bash
cd sources/UI && npm run test
```

**Rule:** Always run `npm run test` after any UI change, `test_pipeline.py` after any API change.

---

## Security

- Sanitize user input to prevent XSS
- Use environment variables for sensitive configuration
- Never expose internal error details to API consumers
- Validate all input with Pydantic models
- Zip extraction: always use `safe_extract_zip()` (blocks path traversal)

---

## Documentation

Consult these before modifying pipeline logic:
- `C4_EXTRACTION_LOGIC.md`
- `CONTEXT_EXTRACTION_GUIDE.md`
- `MOTHER_COMMANDS.md`

Keep `IMPLEMENTATION_STATUS.md` updated.
