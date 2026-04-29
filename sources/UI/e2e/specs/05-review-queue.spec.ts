import { test, expect } from '@playwright/test';

test.describe('Review Queue', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/review');
    await page.waitForLoadState('networkidle');
  });

  test('page loads with Review Queue heading', async ({ page }) => {
    await expect(page.locator('h1').filter({ hasText: 'Review Queue' })).toBeVisible({ timeout: 10000 });
  });

  test('shows extraction run ID input and Load button', async ({ page }) => {
    await expect(page.locator('input[placeholder="Extraction run ID"]')).toBeVisible();
    await expect(page.getByRole('button', { name: /load/i })).toBeVisible();
  });

  test('shows Bulk Approve button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /bulk approve/i })).toBeVisible();
  });

  test('renders review table when items exist, or empty state if none', async ({ page }) => {
    const emptyState = page.locator('p').filter({ hasText: 'No pending items' });
    const table = page.locator('table');

    const hasTable = (await table.count()) > 0;

    if (hasTable) {
      await expect(table).toBeVisible();
      await expect(page.locator('th').filter({ hasText: 'Confidence' })).toBeVisible();
      await expect(page.locator('th').filter({ hasText: 'Field' })).toBeVisible();
      await expect(page.locator('th').filter({ hasText: 'Actions' })).toBeVisible();
    } else {
      await expect(emptyState).toBeVisible();
    }
  });

  test('shows pending item count', async ({ page }) => {
    const countText = page.locator('p').filter({ hasText: /pending items|pending item/ }).last();
    await expect(countText).toBeVisible();
  });

  test('action buttons present when review items exist', async ({ page }) => {
    const table = page.locator('table');
    const hasItems = (await table.count()) > 0 && (await table.locator('tbody tr').count()) > 0;

    if (hasItems) {
      await expect(page.getByRole('button', { name: /^Approve$/ })).toBeVisible();
      await expect(page.getByRole('button', { name: /^Reject$/ })).toBeVisible();
      await expect(page.getByRole('button', { name: /^Override$/ })).toBeVisible();
    }
  });
});
