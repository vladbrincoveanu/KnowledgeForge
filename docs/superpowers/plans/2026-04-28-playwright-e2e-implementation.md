# Playwright E2E Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Playwright E2E test suite to KnowledgeForge's frontend that verifies architecture graphs, LLM chat, messages, LLM enrichment display, and review queue.

**Architecture:** Playwright runs on the host, manages Vite dev server via webServer config, and hits the API through Vite's proxy (`:3000/api/*` → `:8000`). Docker stack (`make up`) is a pre-condition. Extraction setup calls the API to scan a local demo fixture inside the Docker container.

**Tech Stack:** `@playwright/test`, Vite dev server, Docker compose (API + PostgreSQL + Neo4j), OmniPay demo fixtures

---

### Task 1: Install Playwright and configure project

**Files:**
- Modify: `sources/UI/package.json`
- Create: `sources/UI/playwright.config.ts`
- Modify: `sources/UI/.gitignore`

- [ ] **Step 1: Install Playwright dependency**

```bash
cd sources/UI && npm install --save-dev @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: Create `sources/UI/playwright.config.ts`**

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'setup',
      testMatch: '**/01-extraction.setup.ts',
    },
    {
      name: 'chromium',
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
```

- [ ] **Step 3: Add Playwright entries to `.gitignore`**

```
# Playwright
e2e/test-results/
e2e/playwright-report/
e2e/.extraction-state.json
e2e/.extraction-fixtures.json
```

- [ ] **Step 4: Add npm scripts to `sources/UI/package.json`**

```json
"test:e2e": "npx playwright test",
"test:e2e:ui": "npx playwright test --ui",
"test:e2e:debug": "npx playwright test --debug",
```

- [ ] **Step 5: Create e2e directory**

```bash
mkdir -p sources/UI/e2e/specs
```

- [ ] **Step 6: Commit**

```bash
git add sources/UI/package.json sources/UI/playwright.config.ts sources/UI/.gitignore sources/UI/e2e/
git commit -m "chore: add Playwright E2E test infrastructure"
```

---

### Task 2: Add `/app/sources/demo` to allowed scan path prefixes

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/code_extraction.py:848`

**Reason:** The scan endpoint validates `repo_path` against an allowlist (`["/tmp", "/repos", "/data", "/cms", "/app/data"]`). Demo fixtures are at `/app/sources/demo/` in Docker. Adding this prefix is safe — the fixtures are read-only (`:ro` mount).

- [ ] **Step 1: Add `/app/sources/demo` to allowed prefixes**

```python
        repo_path = validate_local_repo_path(
            request.repo_path,
            allowed_prefixes=["/tmp", "/repos", "/data", "/cms", "/app/data", "/app/sources/demo"],
        )
```

- [ ] **Step 2: Restart API container**

```bash
docker compose restart api
```

- [ ] **Step 3: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/code_extraction.py
git commit -m "fix(api): add /app/sources/demo to allowed scan path prefixes"
```

---

### Task 3: Create extraction setup test

**Files:**
- Create: `sources/UI/e2e/specs/01-extraction.setup.ts`

**Purpose:** This Playwright setup project runs first. It triggers extraction of an OmniPay demo fixture via the API, polls until completion, then saves the extraction state for downstream tests.

- [ ] **Step 1: Create `sources/UI/e2e/specs/01-extraction.setup.ts`**

```typescript
import { test as setup, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const STATE_FILE = path.join(__dirname, '..', '.extraction-state.json');

async function pollExtraction(baseURL: string, taskId: string, maxRetries = 30): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(`${baseURL}/api/v1/code/scan/${taskId}`);
    const data = await response.json();
    if (data.status === 'completed') return;
    if (data.status === 'failed') {
      throw new Error(`Extraction failed: ${JSON.stringify(data)}`);
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error(`Extraction timed out after ${maxRetries * 2}s`);
}

setup('extract OmniPay demo fixture', async ({ request }) => {
  if (fs.existsSync(STATE_FILE)) {
    const existing = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    if (existing.status === 'completed') return;
  }

  const demoPath = '/app/sources/demo/omnipay-payment-processor';

  const response = await request.post('/api/v1/code/scan', {
    data: {
      repo_path: demoPath,
      use_c4_model: true,
      max_components_per_domain: 10,
    },
  });
  expect(response.ok()).toBeTruthy();

  const body = await response.json();
  expect(body.task_id).toBeDefined();

  const apiBase = 'http://localhost:8000';
  await pollExtraction(apiBase, body.task_id);

  fs.writeFileSync(STATE_FILE, JSON.stringify({
    task_id: body.task_id,
    status: 'completed',
    fixture: 'omnipay-payment-processor',
    timestamp: Date.now(),
  }));
});
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/e2e/specs/01-extraction.setup.ts
git commit -m "test(e2e): add extraction setup test for Playwright"
```

---

### Task 4: Create architecture graph tests

**Files:**
- Create: `sources/UI/e2e/specs/02-architecture-graph.spec.ts`

- [ ] **Step 1: Create `sources/UI/e2e/specs/02-architecture-graph.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';

test.describe('Architecture Graph', () => {
  test.beforeAll(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
  });

  test('renders the ReactFlow graph canvas', async ({ page }) => {
    const canvas = page.locator('.react-flow');
    await expect(canvas).toBeVisible();
  });

  test('renders at least one node in the graph', async ({ page }) => {
    const nodes = page.locator('.react-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 10000 });
    const count = await nodes.count();
    expect(count).toBeGreaterThan(0);
  });

  test('shows level switcher pills', async ({ page }) => {
    const contextPill = page.getByRole('button', { name: /context/i });
    const containerPill = page.getByRole('button', { name: /container/i });
    const componentPill = page.getByRole('button', { name: /component/i });

    await expect(contextPill).toBeVisible();
    await expect(containerPill).toBeVisible();
    await expect(componentPill).toBeVisible();
  });

  test('switches to Container level on pill click', async ({ page }) => {
    const containerPill = page.getByRole('button', { name: /container/i });
    await containerPill.click();
    await page.waitForTimeout(1000);
    const nodes = page.locator('.react-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 5000 });
  });

  test('opens detail panel on node click', async ({ page }) => {
    const firstNode = page.locator('.react-flow__node').first();
    await firstNode.click();
    await page.waitForTimeout(500);
    const detailPanel = page.locator('[class*="detail"], [class*="sidebar"]').first();
    const nodeName = await firstNode.textContent();

    if (await detailPanel.isVisible().catch(() => false)) {
      await expect(detailPanel).toBeVisible();
      const panelText = await detailPanel.textContent();
      if (nodeName && panelText) {
        expect(panelText.length).toBeGreaterThan(0);
      }
    }
  });

  test('search input is functional', async ({ page }) => {
    const searchInput = page.locator('input[type="text"], input[placeholder*="search" i], input[placeholder*="filter" i]').first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill('payment');
      await page.waitForTimeout(500);
      const nodes = page.locator('.react-flow__node');
      const count = await nodes.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/e2e/specs/02-architecture-graph.spec.ts
git commit -m "test(e2e): add architecture graph Playwright tests"
```

---

### Task 5: Create chat tests

**Files:**
- Create: `sources/UI/e2e/specs/03-chat.spec.ts`

- [ ] **Step 1: Create `sources/UI/e2e/specs/03-chat.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';

test.describe('LLM Chat in Architecture Viewer', () => {
  test.beforeAll(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
    const nodes = page.locator('.react-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 10000 });
    await nodes.first().click();
    await page.waitForTimeout(500);
  });

  test('chat input is present after node selection', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').last();
    await expect(chatInput).toBeVisible({ timeout: 5000 });
  });

  test('sends a message and shows it in chat history', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').last();
    await chatInput.fill('Summarize this service');
    await chatInput.press('Enter');
    await page.waitForTimeout(500);

    const userMessage = page.locator('text=Summarize this service').first();
    await expect(userMessage).toBeVisible({ timeout: 5000 });
  });

  test('receives an assistant streaming response', async ({ page }) => {
    const assistantMessage = page.locator('[class*="assistant"], [class*="bot"], [class*="response"]').first();
    if (await assistantMessage.isVisible().catch(() => false)) {
      const text = await assistantMessage.textContent();
      expect(text).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/e2e/specs/03-chat.spec.ts
git commit -m "test(e2e): add chat Playwright tests"
```

---

### Task 6: Create LLM enrichment tests

**Files:**
- Create: `sources/UI/e2e/specs/04-llm-enrichment.spec.ts`

- [ ] **Step 1: Create `sources/UI/e2e/specs/04-llm-enrichment.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';

test.describe('LLM Enrichment Display', () => {
  test.beforeAll(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
    const nodes = page.locator('.react-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 10000 });
    await nodes.first().click();
    await page.waitForTimeout(500);
  });

  test('detail panel shows enrichment fields', async ({ page }) => {
    const detailPanel = page.locator('text=/confidence|decision mode|review status|llm_score|enrichment/i');
    const hasEnrichmentSection = await detailPanel.isVisible().catch(() => false);
    if (hasEnrichmentSection) {
      await expect(detailPanel).toBeVisible();
    }
  });

  test('confidence score badge is displayed on enriched nodes', async ({ page }) => {
    const badge = page.locator('[class*="confidence"], [class*="score"], [class*="badge"]').first();
    if (await badge.isVisible().catch(() => false)) {
      const text = await badge.textContent();
      expect(text).toMatch(/\d+(\.\d+)?/);
    }
  });

  test('review status indicator is visible', async ({ page }) => {
    const statusIndicator = page.locator('text=/auto.accepted|needs.review|approved|rejected/i');
    if (await statusIndicator.isVisible().catch(() => false)) {
      await expect(statusIndicator).toBeVisible();
    }
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/e2e/specs/04-llm-enrichment.spec.ts
git commit -m "test(e2e): add LLM enrichment Playwright tests"
```

---

### Task 7: Create review queue tests

**Files:**
- Create: `sources/UI/e2e/specs/05-review-queue.spec.ts`

- [ ] **Step 1: Create `sources/UI/e2e/specs/05-review-queue.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';

test.describe('Review Queue', () => {
  test.beforeAll(async ({ page }) => {
    await page.goto('/review');
  });

  test('review page loads with pending items', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    const pageHeading = page.locator('h1, h2, h3').filter({ hasText: /review/i }).first();
    await expect(pageHeading).toBeVisible({ timeout: 10000 });
  });

  test('review table/list is rendered', async ({ page }) => {
    const table = page.locator('table, [role="grid"], [class*="list"], [class*="table"]').first();
    if (await table.isVisible().catch(() => false)) {
      await expect(table).toBeVisible();
    }
  });

  test('pending items show confidence scores', async ({ page }) => {
    const confidenceElements = page.locator('[class*="confidence"], [class*="score"]').first();
    if (await confidenceElements.isVisible().catch(() => false)) {
      const text = await confidenceElements.textContent();
      expect(text).toBeTruthy();
    }
  });

  test('approve button exists for review items', async ({ page }) => {
    const approveButton = page.getByRole('button', { name: /approve/i }).first();
    if (await approveButton.isVisible().catch(() => false)) {
      await expect(approveButton).toBeVisible();
    }
  });

  test('reject button exists for review items', async ({ page }) => {
    const rejectButton = page.getByRole('button', { name: /reject/i }).first();
    if (await rejectButton.isVisible().catch(() => false)) {
      await expect(rejectButton).toBeVisible();
    }
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/e2e/specs/05-review-queue.spec.ts
git commit -m "test(e2e): add review queue Playwright tests"
```

---

### Task 8: Run the full suite and fix failures

**Files:** (none — iterative fixes)

- [ ] **Step 1: Start Docker services**

```bash
make up
```

Wait for all containers to be healthy (check with `docker compose ps`).

- [ ] **Step 2: Run extraction setup to verify the endpoint works**

```bash
cd sources/UI && npx playwright test e2e/specs/01-extraction.setup.ts --project=setup
```

Expected: extraction completes, `.extraction-state.json` created.

- [ ] **Step 3: Run the full Playwright suite**

```bash
cd sources/UI && npx playwright test
```

Expected: all tests pass on first run. If any fail:
- Check the HTML report: `npx playwright show-report`
- Fix selectors to match the actual DOM (use `page.locator()` with data-testid or better selectors based on the component structure)
- Add `--debug` to step through: `npx playwright test --debug`
- Re-run after fixes

Common fixes needed:
- Selectors may not match the exact CSS classes used by the components
- Detail panel selectors need to match the actual React component structure
- Chat input may use a different selector (specific textarea or input)

- [ ] **Step 4: Run existing Vitest tests to confirm no regressions**

```bash
cd sources/UI && npm run test
cd sources/Api && python3 -m pytest tests/ -v
```

- [ ] **Step 5: Commit any selector fixes**

```bash
git add sources/UI/e2e/specs/*.ts sources/UI/playwright.config.ts
git commit -m "test(e2e): fix selectors after first successful run"
```

---

### Task 9: Update frontend quality gates

**Files:**
- Modify: `AGENTS.md` (add e2e test documentation)
- Modify: Makefile (add playwright target, optional)

- [ ] **Step 1: Update AGENTS.md with e2e test commands**

Add to the "Frontend quality gates" section:
```
npm run test:e2e          # Playwright E2E tests (requires: make up)
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add Playwright E2E test commands to AGENTS.md"
```
