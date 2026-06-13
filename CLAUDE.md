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

**Backend Tests:**
```bash
# All tests
docker compose exec api python -m pytest tests/ -v

# Single test file
docker compose exec api python -m pytest tests/unit/services/c4/test_context_manager.py -v

# Tests matching a keyword
docker compose exec api python -m pytest tests/ -k "test_owner" -v

# Full E2E regression suite (11-test gate — run before any merge)
docker compose exec api python -m pytest test_e2e_extraction.py -v

# OmniPay demo tests
docker compose exec api python -m pytest tests/e2e/test_omnipay_extraction.py -v
```

**Frontend:**
```bash
cd sources/UI
npm run fix-all      # prettier + eslint fixes
npm run check-all    # type-check + lint + format check
npm run test         # all tests (mandatory before declaring done)
```

---

## Architecture

### Workspace Separation

```
sources/Api/app/services/c4/graphify_*.py  # Active extraction pipeline — OUR WORKSPACE
sources/Api/app/services/c4/containers/    # Container detection — OTHER SQUAD'S WORKSPACE
sources/Api/app/services/c4/context/       # Legacy context extractors — bypassed, do not delete (tests)
sources/Api/app/services/c4/components/    # Legacy component extractors — bypassed, do not delete (tests)
sources/Api/app/services/c4/enrichment/    # Legacy LLM enrichment — bypassed, do not delete (tests)
```

**Do NOT modify `containers/`** unless explicitly coordinating with the other developer.

### Extraction Pipeline

```
GitHub URL → github_downloader.py (clone with full_history=True)
    → GraphifyC4Extractor (graphify_c4_extractor.py)
        → graphify_runner.py     — runs Graphify CLI (Tree-sitter AST, 36+ languages) → graph.json
        → graphify_summarizer.py — compresses graph: god nodes, communities, external imports
        → graphify_llm.py        — calls minimax/minimax-m3 via OpenRouter → C4 JSON
    → GraphWriter (graph_writer.py) → Neo4j
```

Key files:
- `sources/Api/app/services/c4/graphify_c4_extractor.py` — pipeline orchestrator
- `sources/Api/app/services/c4/graphify_runner.py` — Graphify subprocess wrapper
- `sources/Api/app/services/c4/graphify_summarizer.py` — graph → LLM context compression
- `sources/Api/app/services/c4/graphify_llm.py` — OpenRouter client + C4 prompt
- `sources/Api/app/services/c4/graph_writer.py` — Neo4j persistence layer

### Required env vars (extraction)

```
OPENROUTER_API_KEY   # OpenRouter API key (already in .env)
OPENROUTER_MODEL     # Model override — defaults to minimax/minimax-m3
```

Graphify runs **code-only** (no LLM tokens) — all upstream LLM keys are stripped before invoking it. Only OpenRouter is used, for C4 inference.

### API Routes

```
GET/POST /api/v1/health/     — liveness + readiness
POST     /api/v1/code/       — trigger C4 extraction (GitHub URL or ZIP upload)
GET/POST /api/v1/review/     — HITL review queue
WS       /ws/{task_id}       — real-time extraction progress stream
GET/PUT  /api/v1/config/llm  — LLM provider configuration
```

### Service Data Format

Each extracted service has **7 primary fields**:
1. `domain` — Business domain (e.g., "ai", "docs", "api")
2. `owner` — From git history (top contributor), never "Unassigned" when git exists
3. `status` — `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown`
4. `tier` — "Tier 1", "Tier 2", "Tier 3", "Unknown"
5. `data_class` — "PII", "Credit-Card", "Internal", "Public", "Unknown"
6. `active_experts` — Bus factor indicator (contributor spread)
7. `compliance` — Architectural compliance risk level

---

## Key Conventions

### Error Handling
- **Never** use bare `except Exception:` (except for 3rd-party LLM calls)
- Use typed exceptions from `app/domain/exceptions.py`

### Pydantic V2
- Strict typing; enums use `.value` for membership checks
- Use `Field()` for validation constraints
- Use `validate_by_name` (NOT `allow_population_by_field_name`)

### Git History
- `full_history=True` required in `github_downloader.py` so Graphify picks up contributor nodes for owner inference

### ServiceStatus Values
Canonical values: `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` — NOT old strings like "Active-Dev"

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
