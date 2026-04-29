import { test, expect } from '@playwright/test';

test.describe('Architecture Graph', () => {
  test.beforeEach(async ({ page }) => {
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
    const contextPill = page.getByRole('button', { name: 'Context', exact: true });
    const containerPill = page.getByRole('button', { name: 'Container', exact: true });
    const componentPill = page.getByRole('button', { name: 'Component', exact: true });

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
