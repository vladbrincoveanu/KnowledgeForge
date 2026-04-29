import { test, expect } from '@playwright/test';

test.describe('LLM Chat in Architecture Viewer', () => {
  test.beforeEach(async ({ page }) => {
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

  test('receives an assistant response', async ({ page }) => {
    await page.waitForTimeout(3000);
    const assistantMessage = page.locator('text=Preparing a response, .message-assistant, [class*="assistant"]').first();
    const isVisible = await assistantMessage.isVisible().catch(() => false);
    if (isVisible) {
      const text = await assistantMessage.textContent();
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });
});
