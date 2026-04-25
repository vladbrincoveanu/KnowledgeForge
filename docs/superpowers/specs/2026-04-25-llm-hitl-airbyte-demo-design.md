# LLM Enrichment + HITL + Airbyte Demo — Design Spec

**Date:** 2026-04-25
**Status:** approved

## Overview

Three interconnected changes to KnowledgeForge:

1. **Add Airbyte monorepo** as a primary demo fixture (real-world monorepo with cross-service dependencies)
2. **LLM enrichment at extraction time** — fill ambiguous fields via LLM and surface low-confidence items to a review queue
3. **Human-in-the-loop UI workflow** — review dashboard where humans approve/reject/override extraction decisions

## Section 1: Demo Project Strategy

OmniPay (23 isolated silo repos) stays for regression tests. Airbyte is added as the showcase extraction target — a real monorepo with inter-service deps, shared libraries, and multiple languages.

```
sources/demo/airbyte/     -- git clone pinned to a release tag, read-only fixture
sources/demo/omnipay-*/   -- existing 23 repos, unchanged
```

### Module: Airbyte Demo Fixture
- **Responsibility:** Provide a pinned, read-only copy of the Airbyte monorepo for extraction
- **Interface:** `sources/demo/airbyte/` directory, referenced by extraction test via local path
- **Dependencies:** Git clone of `github.com/airbytehq/airbyte` pinned to a specific release tag
- **Size target:** Fixture only — no code to write, just a clone script reference + test assertions

## Section 2: LLM Enrichment + HITL Architecture

### Pipeline Flow

```
GitHub/local repo → Deterministic Extraction
    ├── confidence >= 0.90 → auto-accept, store
    ├── confidence 0.70-0.89 → LLM adjudicate, store with warning
    └── confidence < 0.70 → route to review queue → HITL UI
```

### LLM-Enriched Fields (at extraction time)

| Field | When LLM fires |
|---|---|
| Container description | Always (replacing generic `"No description"`) |
| Relationship description | When dependency type is unclear |
| Business domain | When keyword match fails |
| Owner team | When CODEOWNERS conflicts or absent |
| Service tier | When deployment signals are ambiguous |

### HITL Review Queue (PostgreSQL)

```python
ReviewItem:
    extraction_run_id: str
    field: str              # e.g. "owner", "tier", "business_domain"
    candidate_values: list  # what the detectors found
    llm_suggestion: str     # what LLM thinks
    confidence: float
    evidence: list[EvidenceItem]  # code snippets, file paths
    status: PENDING | APPROVED | REJECTED | OVERRIDDEN
    reviewer_note: str      # human-provided correction
```

### HITL Review API (`/api/v1/review/`)

| Method | Path | Action |
|---|---|---|
| GET | `/pending?run_id=X` | List pending review items |
| POST | `/{item_id}/approve` | Accept LLM suggestion |
| POST | `/{item_id}/reject` | Reject, fallback to heuristic |
| POST | `/{item_id}/override` | Provide manual value |
| POST | `/{run_id}/bulk-approve` | Approve all ≥ 0.85 confidence items |

### HITL Review UI

- Route: `/review` in React frontend
- Lists all pending review items per extraction run
- Each item shows: field name, candidates, LLM suggestion, evidence snippets
- Actions: Approve / Reject / Override (type your own value)
- Bulk approve for high-confidence items
- After review, corrected values flow back into the C4 graph

## Section 3: Implementation Modules

### Module: Extraction Pipeline — LLM Enhancement Pass
- **Responsibility:** At extraction time, send ambiguous fields to LLM for enrichment and surface low-confidence items to the review queue
- **Interface:** Called by `ContextManager.extract_context()` and `ContainerManager` after deterministic detection. Reads `confidence` from `ExtractionDecision`. Writes `ReviewItem` to PostgreSQL.
- **Dependencies:** `LLMManager`, PostgreSQL `review_items` table, existing detector classes (`context_manager.py`, `container_manager.py`, `metadata_detector.py`)
- **Size target:** ~150 lines (thin orchestration layer; reuses existing LLM + detector infrastructure)

### Module: Review API
- **Responsibility:** CRUD API for reviewing and resolving extraction decisions
- **Interface:** REST endpoints under `/api/v1/review/` — list pending, approve, reject, override, bulk-approve
- **Dependencies:** FastAPI router, PostgreSQL `review_items` table, Pydantic schemas
- **Size target:** ~200 lines (5 endpoints + schemas)

### Module: Review Dashboard UI
- **Responsibility:** Display pending review items, let humans approve/reject/override extraction decisions
- **Interface:** React route `/review`, consumes Review API endpoints, emits decisions back
- **Dependencies:** React Router, existing UI component library (Axios, toast), ReactFlow for context diagram integration
- **Size target:** ~250 lines (table view + action modals + inline override form)

### Module: Airbyte Extraction E2E Tests
- **Responsibility:** Validate extraction pipeline against the Airbyte monorepo
- **Interface:** `tests/e2e/test_airbyte_extraction.py` with test classes mirroring OmniPay structure
- **Dependencies:** pytest, Docker API service, `sources/demo/airbyte/` fixture
- **Size target:** ~400 lines

### Module: HITL Review Workflow E2E Tests
- **Responsibility:** Validate the full review workflow: low-confidence item → queue → human action → re-extraction
- **Interface:** `tests/e2e/test_hitl_review_workflow.py`
- **Dependencies:** pytest, Docker API service, Review API, `FakeOmniPayLLM`
- **Size target:** ~200 lines

## Constraints

- OmniPay tests MUST NOT regress — the existing 12 test classes (~40 methods) remain green
- `sources/Api/app/services/c4/containers/` — do not modify (parallel squad's territory)
- LLM enrichment is non-destructive: never overwrites confident deterministic results
- Airbyte fixture must be pinned to a specific release tag for reproducible extraction
