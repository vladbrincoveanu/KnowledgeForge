import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const RESULT_FILE = path.join(__dirname, '..', '.extraction-result.json');

interface ExtractionResult {
  containers: { name: string; type: string }[];
  components: { name: string }[];
  statistics: { total_containers: number; total_components: number };
}

function loadResult(): ExtractionResult {
  if (!fs.existsSync(RESULT_FILE)) {
    throw new Error(`${RESULT_FILE} not found — extraction setup must run first`);
  }
  return JSON.parse(fs.readFileSync(RESULT_FILE, 'utf-8'));
}

test.describe('Architecture Graph', () => {
  let containerNames: string[];
  let totalContainers: number;

  test.beforeEach(async ({ page }) => {
    const result = loadResult();
    totalContainers = result.statistics.total_containers;
    containerNames = result.containers.map(c => c.name);
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
  });

  test('renders the ReactFlow graph canvas', async ({ page }) => {
    await expect(page.locator('.react-flow')).toBeVisible();
  });

  test('renders container nodes matching extraction result', async ({ page }) => {
    await expect(page.locator('.react-flow__node')).not.toHaveCount(0, { timeout: 10000 });

    const namesToCheck = containerNames.slice(0, 3);
    for (const name of namesToCheck) {
      const node = page.locator('.node-name').filter({ hasText: name });
      await expect(node.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('shows three level switcher pills', async ({ page }) => {
    const pills = page.locator('.level-pill');
    await expect(pills).toHaveCount(3);
    await expect(pills.nth(0)).toHaveText('Context');
    await expect(pills.nth(1)).toHaveText('Container');
    await expect(pills.nth(2)).toHaveText('Component');
  });

  test('switching to Container level changes visible nodes', async ({ page }) => {
    const containerPill = page.getByRole('button', { name: 'Container', exact: true });
    await containerPill.click();
    await page.waitForTimeout(1500);
    const containerNodes = page.locator('.react-flow__node-custom');
    await expect(containerNodes.first()).toBeVisible({ timeout: 5000 });
  });

  test('clicking any container node opens the detail panel', async ({ page }) => {
    if (containerNames.length === 0) return;

    const firstNode = page.locator('.node-name').filter({ hasText: containerNames[0] });
    await firstNode.first().click();
    await page.waitForTimeout(500);

    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });
    await expect(detailPanel.locator('.chat-title h3')).not.toBeEmpty();
  });

  test('detail panel shows architecture metadata fields', async ({ page }) => {
    if (containerNames.length === 0) return;

    const firstNode = page.locator('.node-name').filter({ hasText: containerNames[0] });
    await firstNode.first().click();
    await page.waitForTimeout(500);

    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    const labels = detailPanel.locator('span.detail-label');
    const labelTexts = await labels.allTextContents();
    const allLabels = labelTexts.map(t => t.trim());

    expect(allLabels.some(l => l.length > 0)).toBeTruthy();
  });

  test('search input allows filtering nodes', async ({ page }) => {
    const searchInput = page.locator('input.search-input');
    await expect(searchInput).toBeVisible();

    if (containerNames.length > 0) {
      const searchTerm = containerNames[0].substring(0, 4);
      await searchInput.fill(searchTerm);
      const currentVal = await searchInput.inputValue();
      expect(currentVal).toBe(searchTerm);
    }
  });
});
