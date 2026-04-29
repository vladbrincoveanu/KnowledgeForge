# Airbyte Demo Integration — Design Spec

**Date:** 2026-04-29
**Status:** approved (brainstorming)

## Overview

The Airbyte v0.63.1 monorepo exists at `sources/demo/airbyte/` but was never wired into the extraction pipeline's default demo or the E2E tests. This spec covers making Airbyte the default bundled demo, upgrading the tests to verify real extraction, and updating the Playwright suite.

## Section 1: Bundled Demo Regeneration

### Current state
`c4_extractor.py:main()` targets `sources/demo/` (all 24 subdirs) and writes `c4_architecture.json`. This file does not currently exist — the bundled demo was never regenerated.

### Change
Point `target_repo` to `sources/demo/airbyte` specifically. The resulting `c4_architecture.json` will contain only Airbyte's containers, components, and dependencies.

### Module: `c4_extractor.py:main()`
- **Responsibility:** Regenerate `c4_architecture.json` from Airbyte monorepo
- **Interface:** Reads `sources/demo/airbyte/`, writes `sources/Api/c4_architecture.json`
- **Dependencies:** Full extraction pipeline (ContainerManager, ContextManager, ComponentExtractor)
- **Size target:** 1-line change (path), plus an optional `max_components_per_domain` tuning

## Section 2: Python E2E Tests

### Current state
`tests/e2e/test_airbyte_extraction.py` has 5 tests that only check file existence (e.g. `build.gradle` exists, `.java` files > 10, `setup.py` exists).

### Change
Replace with a single integration test that:
1. Calls `POST /api/v1/code/scan` with path `/app/sources/demo/airbyte`
2. Polls `GET /api/v1/code/scan/{task_id}` until `status: completed`
3. Validates: `containers_count > 0`, `components_count > 0`, `external_deps_count > 0`
4. Validates extraction quality: at least 1 container has a detected `technology` field, at least 1 external dependency is mapped, at least 1 component has a name

The old file-existence checks can be removed or moved to a simpler smoke test.

### Module: `test_airbyte_extraction.py`
- **Responsibility:** Verify C4 pipeline extracts meaningful architecture from Airbyte
- **Interface:** REST API scan + poll
- **Dependencies:** Docker with API running, Airbyte fixture mounted at `/app/sources/demo/airbyte`
- **Size target:** ~80 lines

## Section 3: Playwright Tests

### Current state
- `01-extraction.setup.ts` scans `omnipay-payment-processor`
- `02-architecture-graph.spec.ts` checks for node name `OmniPay Payment Processor`, labels `Owner Team`, `Business Domain`
- `03-chat.spec.ts`, `04-llm-enrichment.spec.ts`, `05-review-queue.spec.ts` all depend on the extraction result

### Change
- Update `01-extraction.setup.ts` to scan `airbyte` instead of `omnipay-payment-processor`
- In `02-architecture-graph.spec.ts`, replace node name assertions with an **inspection step**: after extraction completes, fetch the result to discover the actual top-level node names, then assert on those dynamically. This avoids brittleness from extraction output changes.
- Remaining spec files (`03-chat.spec.ts`, `04-llm-enrichment.spec.ts`, `05-review-queue.spec.ts`) are already generic — they check structural elements (detail panel, metadata fields, chat input, review queue) rather than hardcoded values. These should work unchanged if the extraction produces valid architecture data.

### Module: `01-extraction.setup.ts` (updated)
- **Responsibility:** Run extraction against Airbyte fixture before Playwright tests
- **Interface:** POST/Poll scan API, save state for downstream tests
- **Dependencies:** Docker API service, Airbyte fixture
- **Size target:** 1-line change (path)

### Module: `02-architecture-graph.spec.ts` (updated)
- **Responsibility:** Verify graph renders nodes from Airbyte extraction
- **Interface:** Same DOM selectors, dynamic node name assertions
- **Dependencies:** Fresh extraction (setup test must complete first)
- **Size target:** ~80 lines

## Section 4: What Stays the Same

- **OmniPay fixtures** remain in `sources/demo/` — CI unit tests (`test_edge_cases.py`, `test_provider_catalog.py`, etc.) need them
- **`_load_default_c4_from_json()`** — unchanged, just reads `c4_architecture.json`
- **`docker-compose.yml`** — unchanged, Airbyte already mounted
- **`.gitignore`** — `c4_architecture.json` is already ignored
- **Review queue tests** — unchanged, they test the review workflow regardless of which demo was extracted

## Section 5: Implementation Order

1. Regenerate `c4_architecture.json` (1 line + run main())
2. Update Python E2E tests (replace file-existence with integration test)
3. Update Playwright setup + graph tests
4. Run full test suite to verify

## Constraints

- OmniPay CI unit tests MUST NOT regress
- `sources/Api/app/services/c4/containers/` — do not modify
- Extraction must complete within the Playwright timeout window
