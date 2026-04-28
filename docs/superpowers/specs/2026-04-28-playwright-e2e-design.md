# Playwright E2E Test Suite for KnowledgeForge

**Date:** 2026-04-28
**Status:** Approved Design

## Overview

Add Playwright-based E2E tests to the KnowledgeForge frontend to verify the core demo functionality: architecture graphs, LLM chat, messages, LLM enrichment display, and the human-in-the-loop review queue. Tests run against the full Docker stack (API + DB + demo fixtures) with the Vite dev server managed by Playwright.

## Architecture

```
User's machine
├── Docker compose (make up)
│   ├── API server (:8000)
│   ├── PostgreSQL
│   └── Neo4j
├── Vite dev server (:3000) — started/stopped by Playwright via webServer config
│   └── Proxies /api/* to :8000
└── Playwright test runner
    └── e2e/specs/*.spec.ts — runs against :3000
```

## Configuration

### Module: Playwright Config
- **Responsibility:** Define test runner settings, web server lifecycle, and reporter configuration.
- **Interface:** `playwright.config.ts` consumed by `@playwright/test` CLI.
- **Dependencies:** None.
- **Size target:** < 40 lines.

Key settings:
- `testDir: './e2e'`
- `timeout: 60000` (extraction may be slow)
- `fullyParallel: false` (extraction setup feeds downstream tests)
- `retries: 0` (local), CI should use 2
- `webServer: { command: 'npm run dev', port: 3000, reuseExistingServer: true }`
- `baseURL: 'http://localhost:3000'`
- `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`

## Test Structure

### Module: Extraction Setup
- **Responsibility:** Trigger an OmniPay demo extraction and wait for completion. Provides the `extraction_run_id` used by downstream tests.
- **Interface:** `test.setup` project type (Playwright project dependency). Reads fixture path from env or defaults to `sources/demo/omnipay-payment-processor`.
- **Dependencies:** Docker stack (API on :8000).
- **Size target:** < 60 lines.

### Module: Architecture Graph Tests
- **Responsibility:** Verify the ReactFlow C4 graph canvas renders correctly with nodes and edges.
- **Interface:** `02-architecture-graph.spec.ts`, depends on extraction setup having completed.
- **Dependencies:** Extraction setup.
- **Size target:** < 120 lines.

Test scenarios:
1. Navigate to `/code-architecture`
2. Verify `.react-flow` canvas element exists
3. Verify nodes are rendered (Cytoscape/ReactFlow node count > 0)
4. Switch between Context → Container → Component levels
5. Click a node → verify detail panel opens with service metadata (owner, status, tier)
6. Verify ghost nodes for unresolved external dependencies
7. Verify search/filter input is functional

### Module: Chat Tests
- **Responsibility:** Verify the LLM chat panel within the architecture viewer works end-to-end.
- **Interface:** `03-chat.spec.ts`, depends on extraction setup.
- **Dependencies:** Extraction setup.
- **Size target:** < 100 lines.

Test scenarios:
1. Navigate to `/code-architecture`, select a node
2. Verify chat panel is present in the detail panel
3. Type a message (e.g., "Summarize this service")
4. Verify user message appears in chat history
5. Verify assistant streaming response arrives and is rendered
6. Verify message formatting (role indicator, content display)

### Module: LLM Enrichment Tests
- **Responsibility:** Verify LLM enrichment data (confidence scores, decision modes, review status) is displayed on relevant nodes.
- **Interface:** `04-llm-enrichment.spec.ts`, depends on extraction setup. Uses `omnipay-billing-llm` fixture for enriched data.
- **Dependencies:** Extraction setup.
- **Size target:** < 100 lines.

Test scenarios:
1. Navigate to `/code-architecture`
2. Select a node from `omnipay-billing-llm` (llm_enriched=true)
3. Verify confidence score badge is displayed (numerical value shown)
4. Verify decision mode badge: `DETERMINISTIC` / `LLM_ADJUDICATED` / `HUMAN_REVIEWED`
5. Verify review status badge: `AUTO_ACCEPTED` or `NEEDS_REVIEW`
6. For `NEEDS_REVIEW` items, verify review controls (approve/reject buttons)

### Module: Review Queue Tests
- **Responsibility:** Verify the human-in-the-loop review dashboard displays pending items and supports approve/reject/override actions.
- **Interface:** `05-review-queue.spec.ts`, depends on extraction setup producing low-confidence items.
- **Dependencies:** Extraction setup.
- **Size target:** < 120 lines.

Test scenarios:
1. Navigate to `/review`
2. Verify pending review items are listed
3. Verify each item displays: field name, confidence score, candidate values
4. Approve an item → verify status update
5. Reject an item → verify status update
6. Override with custom value → verify custom value is accepted

## File Layout

```
sources/UI/
├── playwright.config.ts          # Playwright configuration
├── e2e/
│   ├── specs/
│   │   ├── 01-extraction.setup.ts
│   │   ├── 02-architecture-graph.spec.ts
│   │   ├── 03-chat.spec.ts
│   │   ├── 04-llm-enrichment.spec.ts
│   │   └── 05-review-queue.spec.ts
│   └── .gitkeep
```

## Dependencies

New dev dependencies in `sources/UI/`:
- `@playwright/test` — test framework
- Playwright browsers (installed via `npx playwright install chromium`)

## Running the Tests

```bash
# Pre-condition: Docker stack must be running
make up

# From sources/UI/
npx playwright install chromium
npx playwright test

# With UI mode for debugging:
npx playwright test --ui

# Single file:
npx playwright test e2e/specs/02-architecture-graph.spec.ts
```

## Error Handling

- If Docker is not running, the extraction setup test will fail with a clear error (connection refused on :8000)
- If the demo fixture is missing, extraction setup skips with a descriptive message
- Trace and screenshot artifacts are captured on first retry for CI debugging
- Web server config catches Vite startup failure and reports it before test execution

## Out of Scope (for this phase)

- Visual regression testing (screenshot comparison)
- Performance/load testing
- Cross-browser testing beyond Chromium
- Tests on the Landing page (static content, rarely changes)
- Tests on the Workspace page (file uploads, ZIP extraction)
- Tests on the Settings page (configuration CRUD)
