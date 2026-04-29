import { test, expect } from '@playwright/test';

test.describe('Architecture Graph', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
  });

  test('renders the ReactFlow graph canvas', async ({ page }) => {
    await expect(page.locator('.react-flow')).toBeVisible();
  });

  test('renders the OmniPay system node', async ({ page }) => {
    await expect(page.locator('.react-flow__node')).not.toHaveCount(0, { timeout: 10000 });
    const systemNode = page.locator('.node-name').filter({ hasText: 'OmniPay Payment Processor' });
    await expect(systemNode).toBeVisible({ timeout: 5000 });
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

  test('clicking a node opens the detail panel with metadata', async ({ page }) => {
    const systemNode = page.locator('.node-name').filter({ hasText: 'OmniPay Payment Processor' });
    await systemNode.click();
    await page.waitForTimeout(500);

    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    await expect(detailPanel.locator('.chat-title h3')).toHaveText('OmniPay Payment Processor');
    await expect(detailPanel.locator('.chat-subtitle')).toHaveText('System');
  });

  test('detail panel shows architecture metadata fields', async ({ page }) => {
    const systemNode = page.locator('.node-name').filter({ hasText: 'OmniPay Payment Processor' });
    await systemNode.click();
    await page.waitForTimeout(500);

    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    const labels = detailPanel.locator('span.detail-label');
    const labelTexts = await labels.allTextContents();
    const allLabels = labelTexts.map(t => t.trim());

    expect(allLabels).toContain('Owner Team');
    expect(allLabels).toContain('Business Domain');
  });

  test('search input allows filtering nodes', async ({ page }) => {
    const searchInput = page.locator('input.search-input');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('OmniPay');
    const currentVal = await searchInput.inputValue();
    expect(currentVal).toBe('OmniPay');
  });
});
