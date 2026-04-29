# Airbyte Demo Integration — Design Spec

**Date:** 2026-04-29
**Status:** approved (brainstorming)

## Overview

The Airbyte v0.63.1 monorepo exists at `sources/demo/airbyte/` and the bundled `sources/Api/c4_architecture.json` already contains Airbyte extraction results (436KB, 12 containers, 20 components, 19 deps). However, the E2E tests and Playwright suite still target `omnipay-payment-processor` (a 5-file Flask service). This spec covers making Airbyte the primary demo, upgrading the tests to verify real extraction quality, and adding an OmniPay regression guard.

## Section 1: Bundled Demo — Already Done

`c4_extractor.py:main()` previously targeted `sources/demo/` (all subdirs), and since Airbyte dominates by file count, the resulting `c4_architecture.json` already contains Airbyte data (12 containers from Dockerfile subdirectories, 20 components, 19 external dependencies). The cold-start `_load_default_c4_from_json()` already returns this.

**No code changes needed.** The bundled demo is already Airbyte. This section documents the current state and adds quality verification.

### Extraction cost
Current Airbyte extraction produces 12 containers in estimated ~30s. The component extraction (tree-sitter parsing) produces 20 components from entry-point files. Actual timing to be measured on first run.

### `c4_architecture.json` lifecycle
Already tracked in git (9 commits). No `.gitignore` change needed — the file is NOT excluded. Developers regenerate via `make generate-demo`.

### Makefile target
```makefile
generate-demo:
    docker compose exec api python -m app.services.code_extraction.c4_extractor
```
Runs inside Docker container to match the runtime environment. Falls back to host Python if Docker is unavailable.

### Module: `c4_extractor.py:main()`
- **Responsibility:** Regenerate `c4_architecture.json` from the full `sources/demo/` directory
- **Interface:** Reads from `sources/demo/`, writes to `sources/Api/c4_architecture.json`
- **Dependencies:** Full extraction pipeline, Docker (for `make generate-demo`)
- **Size target:** No code change needed (already works)

## Section 2: Python E2E Tests

### Current state
`tests/e2e/test_airbyte_extraction.py` has 5 tests that only check file existence (e.g. `build.gradle` exists, `.java` files > 10, `setup.py` exists).

### Change
Replace with a single integration test that:
1. Calls `POST /api/v1/code/scan` with path `/app/sources/demo/airbyte`
2. Polls `GET /api/v1/code/scan/{task_id}` until `status: completed`
3. Validates: `containers_count > 0`, `components_count > 0`, `external_deps_count > 0`
4. Validates extraction quality: at least 1 container has a detected `technology` field, at least 1 external dependency is mapped, at least 1 component has a name
5. Times the extraction and logs it (baseline for future perf regressions)

### Minimum viable extraction threshold
Based on the existing 436KB `c4_architecture.json`:
- **≥ 2 containers** (Airbyte has 12 today — set a floor that prevents total regression)
- **≥ 1 container with technology populated** (currently 5 of 12 have technology)
- **≥ 1 external dependency** (currently 19)
- **≥ 3 components** (currently 20)

All checks FAIL on failure — no silent skips. If extraction drops below 2 containers, something is broken.

The `test_airbyte_extraction.py` imports use `from app.services...` with `DEMO_AIRBYTE_PATH = Path("/app/sources/demo/airbyte")` — these paths work in Docker but NOT on the host. The test will be run inside Docker via `docker compose exec api`.

### OmniPay retention
Playwright tests switch to Airbyte, but we add a **separate lightweight Playwright test** (`06-omnipay-smoke.spec.ts`) that scans `omnipay-payment-processor` and verifies ≥ 1 container extracted. This catches regressions in OmniPay extraction.

The old Python file-existence checks are removed — they neither test extraction quality nor catch regressions.

### Module: `test_airbyte_extraction.py`
- **Responsibility:** Verify C4 pipeline extracts meaningful architecture from Airbyte
- **Interface:** REST API scan + poll via `docker compose exec`
- **Dependencies:** Docker with API running, Airbyte fixture mounted at `/app/sources/demo/airbyte`
- **Size target:** ~80 lines

## Section 3: Playwright Tests

### Current state
- `01-extraction.setup.ts` scans `omnipay-payment-processor`
- `02-architecture-graph.spec.ts` checks for node name `OmniPay Payment Processor`, labels `Owner Team`, `Business Domain`
- `03-chat.spec.ts`, `04-llm-enrichment.spec.ts`, `05-review-queue.spec.ts` depend on extraction

### Change
- Update `01-extraction.setup.ts` to scan `airbyte` instead of `omnipay-payment-processor`
- After extraction completes, **save the full result** (from `GET /api/v1/code/scan/{task_id}/results`) to a temp file at `e2e/.extraction-result.json`. Format:
  ```json
  {
    "containers": [{"name": "openapi2jsonschema", ...}],
    "components": [...],
    "system_context": {...},
    "relationships": {...},
    "statistics": {"total_containers": 12, "total_components": 20, ...}
  }
  ```
- This file is in `.gitignore` (transient test artifact) and cleaned up on each run
- In `02-architecture-graph.spec.ts`, read the saved result, extract the first 3 container names, and assert those `.node-name` elements exist in the ReactFlow DOM
- Add `06-omnipay-smoke.spec.ts` — scans `omnipay-payment-processor`, verifies ≥ 1 container extracted

### Playwright timeout budget
| Phase | Estimate | Config |
|-------|----------|--------|
| Extraction (Airbyte) | 90s | `playwright.config.ts` project-level timeout: 120s |
| Playwright per-test | 30s | Default (unchanged) |
| Total suite | 5 min | Worker timeout |

Set the setup project's `timeout: 120_000` in `playwright.config.ts` projects array.

### Module: `01-extraction.setup.ts` (updated)
- **Responsibility:** Run extraction against Airbyte fixture, save result for downstream tests
- **Interface:** POST/Poll `POST /api/v1/code/scan`, `GET /results`, write `e2e/.extraction-result.json`
- **Dependencies:** Docker API service, Airbyte fixture
- **Size target:** ~15 lines added

### Module: `02-architecture-graph.spec.ts` (updated)
- **Responsibility:** Verify graph renders nodes from Airbyte extraction (no hardcoded names)
- **Interface:** Reads `e2e/.extraction-result.json`, asserts DOM nodes match discovered container names
- **Dependencies:** Setup test must have saved the extraction result
- **Size target:** ~90 lines

### Module: `06-omnipay-smoke.spec.ts` (new)
- **Responsibility:** Verify OmniPay extraction still works (regression guard)
- **Interface:** Self-contained — calls `POST /api/v1/code/scan` with `omnipay-payment-processor`, polls, asserts ≥ 1 container extracted. No dependency on `01-extraction.setup.ts` (which scans Airbyte)
- **Dependencies:** Docker API service, OmniPay fixture
- **Size target:** ~40 lines

### Remaining spec files
`03-chat.spec.ts`, `04-llm-enrichment.spec.ts`, `05-review-queue.spec.ts` are already generic — they check structural elements (detail panel, metadata fields, chat input, review queue) rather than hardcoded values. These should work unchanged if the extraction produces valid architecture data.

## Section 4: What Stays the Same

- **OmniPay fixtures** remain in `sources/demo/` — CI unit tests (`test_edge_cases.py`, `test_provider_catalog.py`, etc.) need them
- **`_load_default_c4_from_json()`** — unchanged, already loads Airbyte data
- **`docker-compose.yml`** — unchanged, Airbyte already mounted
- **`.gitignore`** — no change needed (c4_architecture.json already tracked, c4_extractions/ paths already ignored)
- **Review queue tests** — unchanged, they test the review workflow regardless of which demo was extracted
- **`sources/Api/app/services/c4/containers/`** — do not modify

## Section 5: Implementation Order

1. **No extraction pipeline changes needed** — `c4_architecture.json` already contains Airbyte. Verify by checking `make generate-demo` works with Docker.
2. Add `e2e/.extraction-result.json` to `.gitignore`
3. Update `01-extraction.setup.ts` (scan Airbyte, save result)
4. Update `02-architecture-graph.spec.ts` (dynamic node names from saved result)
5. Add `06-omnipay-smoke.spec.ts` (self-contained OmniPay extraction + assertion)
6. Update `test_airbyte_extraction.py` (file-existence → integration test)
7. Set Playwright setup timeout to 120s
8. Run full test suite: `npm run test:e2e` + `make tests` + `npm run test` (Vitest)

## Constraints

- OmniPay CI unit tests MUST NOT regress
- OmniPay E2E coverage retained via `06-omnipay-smoke.spec.ts`
- `sources/Api/app/services/c4/containers/` — do not modify
- Extraction must produce ≥ 2 containers, ≥ 3 components, ≥ 1 dependency to pass
- `e2e/.extraction-result.json` is transient (`.gitignore`d, cleaned on each run)
