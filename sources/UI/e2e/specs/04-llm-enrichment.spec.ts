import { test, expect } from '@playwright/test';

test.describe('LLM Enrichment Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
    const systemNode = page.locator('.node-name').filter({ hasText: 'OmniPay Payment Processor' });
    await systemNode.click();
    await page.waitForTimeout(500);
  });

  test('detail panel is visible with metadata for the selected node', async ({ page }) => {
    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });
    await expect(detailPanel.locator('.chat-title h3')).not.toBeEmpty();
  });

  test('compliance fields are present in the metadata', async ({ page }) => {
    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    const labels = detailPanel.locator('span.detail-label');
    const labelTexts = await labels.allTextContents();
    const allLabels = labelTexts.map(t => t.trim());

    expect(allLabels).toContain('Compliance Confidence');
    expect(allLabels).toContain('Architectural Compliance');
  });

  test('decision mode label is rendered when enrichment data exists', async ({ page }) => {
    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    const decisionModeRow = detailPanel.locator('.detail-row').filter({
      has: page.locator('span.detail-label', { hasText: 'Decision Mode' }),
    });
    const rowCount = await decisionModeRow.count();

    if (rowCount > 0) {
      const value = await decisionModeRow.locator('span.detail-value').textContent();
      expect(['Deterministic', 'LLM Adjudicated', 'Human Reviewed']).toContain(value?.trim());
    }
  });

  test('review status label is rendered when enrichment data exists', async ({ page }) => {
    const detailPanel = page.locator('aside.node-details-panel');
    await expect(detailPanel).toBeVisible({ timeout: 3000 });

    const reviewStatusRow = detailPanel.locator('.detail-row').filter({
      has: page.locator('span.detail-label', { hasText: 'Review Status' }),
    });
    const rowCount = await reviewStatusRow.count();

    if (rowCount > 0) {
      const value = await reviewStatusRow.locator('span.detail-value').textContent();
      expect(['Auto Accepted', 'Needs Human Review', 'Approved', 'Rejected']).toContain(value?.trim());
    }
  });
});
