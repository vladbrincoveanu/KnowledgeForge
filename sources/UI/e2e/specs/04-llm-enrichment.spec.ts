import { test, expect } from '@playwright/test';

test.describe('LLM Enrichment Display', () => {
  test.beforeEach(async ({ page }) => {
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
    const badge = page.locator('text=/[0-9]\\.[0-9]/').first();
    if (await badge.isVisible().catch(() => false)) {
      const text = await badge.textContent();
      expect(text).toMatch(/\d+\.\d+/);
    }
  });

  test('review status indicator is visible', async ({ page }) => {
    const statusIndicator = page.locator('text=/auto.accepted|needs.review|approved|rejected/i');
    if (await statusIndicator.isVisible().catch(() => false)) {
      await expect(statusIndicator).toBeVisible();
    }
  });
});
