# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KnowledgeForge is a C4 architecture extraction engine that analyzes codebases and produces structured C4-level graphs (Context, Container, Component, Code). It transforms messy repositories into graph insights stored in Neo4j.

**Stack:** FastAPI (Backend) | React/TypeScript (Frontend) | Neo4j (Graph) | PostgreSQL (Metadata) | Docker

## Mother Commands

Always run these after implementing changes:

```bash
make quick-check    # Fast restart + tests (1-2 min) - use for most changes
make full-check     # Complete rebuild + tests (5-10 min) - use for infrastructure changes
make ci             # CI/CD pipeline simulation - use before merging
```

**E2E Tests:** 11 tests in `sources/Api/test_e2e_extraction.py` + OmniPay demo tests in `sources/Api/tests/e2e/test_omnipay_extraction.py`

## Architecture

### Workspace Separation (The "Iron Curtain")

```
sources/Api/app/services/c4/context/     # Context-level extraction - OUR WORKSPACE
sources/Api/app/services/c4/containers/   # Container-level extraction - OTHER SQUAD'S WORKSPACE
```

Do NOT modify `containers/` unless explicitly coordinating with the other developer.

### Extraction Pipeline

```
GitHub URL → ServiceDiscovery → Language/API/Deployment Detection
    → ServiceEnhancers (8 phases: compliance, docs, comms, auth, etc.)
    → Neo4j (graph) + PostgreSQL (metadata)
```

Key files:
- `sources/Api/app/services/service_extraction/service_enhancers.py` - Enhancement chain
- `sources/Api/app/services/c4/context/context_manager.py` - Context extraction orchestrator
- `sources/Api/app/services/c4/containers/container_manager.py` - Container extraction

### Service Data Format

Each extracted service has **5 primary fields**:
1. `domain` - Business domain (e.g., "ai", "docs", "api")
2. `owner` - From git history (top contributor), never "Unassigned" when git exists
3. `status` - "Active-Dev", "Maintenance-Only", "Deprecated / Frozen"
4. `tier` - "Tier 1", "Tier 2", "Tier 3", "Unknown"
5. `data_class` - "PII", "Credit-Card", "Internal", "Public", "Unknown"

## Development Commands

```bash
# API (runs inside Docker)
docker compose exec api python -m pytest tests/ -v           # Unit tests
docker compose exec api python -m pytest test_e2e_extraction.py -v  # E2E tests
docker compose exec api python tests/test_pipeline.py        # Pipeline integration

# UI (run from sources/UI)
npm run test          # Vitest tests
npm run fix-all       # Format + lint + type-check
npm run check-all     # Validate without fixing

# Standalone
make test-e2e-omnipay        # OmniPay demo E2E tests
make test-owner              # Owner detection test
make test-containers         # Container detection test
```

## Key Conventions

- **Error handling:** Never use bare `except Exception:` (except for 3rd-party LLM calls)
- **Pydantic:** Use V2 with strict typing; enums use `.value` for membership checks
- **Git history:** `full_history=True` required for accurate owner detection
- **ServiceStatus values:** `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED`, `unknown` (NOT old strings)
- **Endpoints:** Extract from Helm `values.yaml`, Ingress, and README docs
- **Zip extraction:** Always use `safe_extract_zip()` to block path traversal
