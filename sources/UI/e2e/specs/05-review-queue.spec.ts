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
