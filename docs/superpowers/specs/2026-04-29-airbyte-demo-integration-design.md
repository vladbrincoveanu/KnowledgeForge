# Airbyte Demo Integration — Design Spec

**Date:** 2026-04-29
**Status:** approved (brainstorming)

## Overview

The Airbyte v0.63.1 monorepo exists at `sources/demo/airbyte/` but was never wired into the extraction pipeline's default demo or the E2E tests. This spec covers making Airbyte the default bundled demo, upgrading the tests to verify real extraction, and updating the Playwright suite.

## Section 1: Bundled Demo Regeneration

### Current state
`c4_extractor.py:main()` targets `sources/demo/` (all 24 subdirs) and writes `c4_architecture.json`. This file does not currently exist.

### Change
Point `target_repo` to `sources/demo/airbyte` specifically. The resulting `c4_architecture.json` will contain only Airbyte's containers, components, and dependencies.

### Extraction cost analysis
The current OmniPay extraction (1 x 5-file Flask service) completes in ~3 seconds. Airbyte is 44 directories, 3000+ files, with Gradle, Java, Python CDK, CI, docusaurus docs. The pipeline runs StructureDetector, ComposeDetector, HelmDetector, K8sDetector, PythonLibraryDetector on the entire tree.

**Estimated extraction time: 30–90 seconds** depending on file I/O and container detection throughput. The Level 3 component extraction (tree-sitter parsing) may dominate. This needs verification — we'll time the first run and document the actual duration.

### `c4_architecture.json` lifecycle
The file will be **committed to git** (small JSON, compressed well). This ensures:
- Playwright tests have a predictable cold-start demo without needing Docker
- CI gets the demo without running extraction
- Developers can regenerate via `make generate-demo` for local testing

The existing `.gitignore` exclusion for `c4_architecture.json` must be removed.

### Makefile target
```makefile
generate-demo:
    cd sources/Api && python3 -m app.services.code_extraction.c4_extractor
```

### Module: `c4_extractor.py:main()`
- **Responsibility:** Regenerate `c4_architecture.json` from Airbyte monorepo
- **Interface:** Reads `sources/demo/airbyte/`, writes `sources/Api/c4_architecture.json`
- **Dependencies:** Full extraction pipeline (ContainerManager, ContextManager, ComponentExtractor)
- **Size target:** 1-line change (path), plus `max_components_per_domain` tuning as needed

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
The extraction must produce:
- **≥ 3 containers** (airbyte-integrations, airbyte-cdk, airbyte-ci at minimum)
- **≥ 1 container with technology populated** (Gradle = Java)
- **≥ 1 external dependency** (database, message queue, or API)
- **≥ 5 components** (from tree-sitter parsing of entry-point files)

If any of these fail, the test FAILS — not skips. An Airbyte that extracts to 1 container named "Airbyte" is a pipeline regression, not a "well, this fixture doesn't support that" case.

The old file-existence checks can be removed or moved to a simpler smoke test.

### OmniPay E2E retention
The Playwright tests switch to Airbyte, but we add a **separate lightweight Playwright test** (`06-omnipay-smoke.spec.ts`) that scans `omnipay-payment-processor` and verifies it still produces valid extraction. This catches regressions in OmniPay extraction even though Airbyte is the default demo.

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
- Save the **full extraction result** (from `GET /results`) to a shared file (`e2e/.extraction-result.json`) in the setup test, so downstream tests can read node names, container count, etc. without hardcoding
- In `02-architecture-graph.spec.ts`, read the saved extraction result to discover container names, then assert those container nodes exist in the ReactFlow canvas. This avoids brittleness: if the pipeline changes output, the tests adapt automatically
- Add `06-omnipay-smoke.spec.ts` — scans `omnipay-payment-processor`, verifies extraction works (basic regression guard)

### Playwright timeout budget
The extraction setup test needs a generous timeout:

| Phase | Estimate | Config |
|-------|----------|--------|
| Extraction (Airbyte) | 90s | `playwright.config.ts` test timeout override |
| Playwright per-test | 30s | Default (unchanged) |
| Total suite | 5 min | Worker timeout |

Set the setup project's timeout to **120 seconds** in `playwright.config.ts` using `test.describe.configure()` or an explicit `timeout` option in the setup test.

### Module: `01-extraction.setup.ts` (updated)
- **Responsibility:** Run extraction against Airbyte fixture, save result for downstream tests
- **Interface:** POST/Poll scan API, GET /results, write `e2e/.extraction-result.json`
- **Dependencies:** Docker API service, Airbyte fixture
- **Size target:** ~15 lines added (save + write result to file)

### Module: `02-architecture-graph.spec.ts` (updated)
- **Responsibility:** Verify graph renders nodes from Airbyte extraction (no hardcoded names)
- **Interface:** Reads `e2e/.extraction-result.json`, asserts DOM nodes match discovered container names
- **Dependencies:** Setup test must have run and saved the extraction result
- **Size target:** ~90 lines

### Module: `06-omnipay-smoke.spec.ts` (new)
- **Responsibility:** Verify OmniPay extraction still works (regression guard)
- **Interface:** Scans `omnipay-payment-processor`, verifies ≥ 1 container extracted
- **Dependencies:** Docker API service, OmniPay fixture
- **Size target:** ~40 lines

### Remaining spec files
`03-chat.spec.ts`, `04-llm-enrichment.spec.ts`, `05-review-queue.spec.ts` are already generic — they check structural elements (detail panel, metadata fields, chat input, review queue) rather than hardcoded values. These should work unchanged if the extraction produces valid architecture data.

## Section 4: What Stays the Same

- **OmniPay fixtures** remain in `sources/demo/` — CI unit tests (`test_edge_cases.py`, `test_provider_catalog.py`, etc.) need them
- **`_load_default_c4_from_json()`** — unchanged, just reads `c4_architecture.json`
- **`docker-compose.yml`** — unchanged, Airbyte already mounted
- **Review queue tests** — unchanged, they test the review workflow regardless of which demo was extracted
- **`sources/Api/app/services/c4/containers/`** — do not modify

## Section 5: Implementation Order

1. Remove `c4_architecture.json` from `.gitignore`
2. Add `generate-demo` target to Makefile
3. Regenerate `c4_architecture.json` (1 line change + run `make generate-demo`)
4. Update Python E2E tests (replace file-existence with integration test)
5. Update Playwright setup test (scan Airbyte, save result to file)
6. Update `02-architecture-graph.spec.ts` (dynamic node names from saved result)
7. Add `06-omnipay-smoke.spec.ts` (OmniPay regression guard)
8. Set Playwright timeout to 120s for setup
9. Run full test suite: `npm run test:e2e` + `python3 -m pytest tests/` + `npm run test` (Vitest)

## Constraints

- OmniPay CI unit tests MUST NOT regress
- OmniPay E2E coverage retained via `06-omnipay-smoke.spec.ts`
- `c4_architecture.json` committed to git (remove from `.gitignore`)
- Extraction time documented after first successful run
- Extraction must produce ≥ 3 containers, ≥ 5 components, ≥ 1 dependency to pass
