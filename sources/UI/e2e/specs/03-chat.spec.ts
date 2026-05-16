import { test, expect } from '@playwright/test';

test.describe('LLM Chat in Architecture Viewer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/code-architecture');
    await page.waitForSelector('.react-flow', { timeout: 15000 });
    const airbyteNode = page.locator('.node-name').filter({ hasText: 'airbyte' });
    await airbyteNode.first().click();
    await page.waitForTimeout(500);
  });

  test('chat input is present in the detail panel after node selection', async ({ page }) => {
    const chatInput = page.locator('textarea[placeholder*="Ask about this node"]');
    await expect(chatInput).toBeVisible({ timeout: 5000 });
  });

  test('send button becomes enabled when chat input has text', async ({ page }) => {
    const sendButton = page.locator('button[aria-label="Send chat message"]');
    await expect(sendButton).toBeVisible();
    await expect(sendButton).toBeDisabled();

    const chatInput = page.locator('textarea[placeholder*="Ask about this node"]');
    await chatInput.fill('Summarize this service');
    await expect(sendButton).toBeEnabled();
  });

  test('sends a message and shows it in chat history', async ({ page }) => {
    const chatInput = page.locator('textarea[placeholder*="Ask about this node"]');
    await chatInput.fill('Summarize this service');

    const sendButton = page.locator('button[aria-label="Send chat message"]');
    await sendButton.click();

    const userMessage = page.locator('.chat-messages').filter({ hasText: 'Summarize this service' });
    await expect(userMessage).toBeVisible({ timeout: 5000 });
  });

});
