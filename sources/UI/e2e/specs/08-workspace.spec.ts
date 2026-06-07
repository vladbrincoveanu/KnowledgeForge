import { test, expect } from "@playwright/test";

test.describe("Workspace — persistent repo queue", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
  });

  test("repo added via URL input persists across tab switch", async ({ page }) => {
    const REPO = "https://github.com/facebook/react";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);
    await urlInput.fill(REPO);
    await page.getByRole("button", { name: /^Add$/i }).click();

    await expect(page.getByText(REPO)).toBeVisible();

    await page.getByRole("link", { name: /Code Architecture/i }).click();
    await expect(page).toHaveURL(/\/code-architecture/);

    await page.getByRole("link", { name: /Workspace/i }).click();
    await expect(page).toHaveURL(/\/workspace/);

    await expect(page.getByText(REPO)).toBeVisible();
  });

  test("two repos can be added and both persist", async ({ page }) => {
    const REPO_A = "https://github.com/facebook/react";
    const REPO_B = "https://github.com/microsoft/typescript";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);

    await urlInput.fill(REPO_A);
    await page.getByRole("button", { name: /^Add$/i }).click();
    await urlInput.fill(REPO_B);
    await page.getByRole("button", { name: /^Add$/i }).click();

    await expect(page.getByText(REPO_A)).toBeVisible();
    await expect(page.getByText(REPO_B)).toBeVisible();

    await page.getByRole("link", { name: /Code Architecture/i }).click();
    await page.getByRole("link", { name: /Workspace/i }).click();

    await expect(page.getByText(REPO_A)).toBeVisible();
    await expect(page.getByText(REPO_B)).toBeVisible();
  });

  test("Remove button removes a repo from the queue", async ({ page }) => {
    const REPO = "https://github.com/facebook/react";
    const urlInput = page.getByPlaceholder(/github\.com\/owner\/repo/i);
    await urlInput.fill(REPO);
    await page.getByRole("button", { name: /^Add$/i }).click();

    await expect(page.getByText(REPO)).toBeVisible();
    await page.locator(`[data-testid="repo-row"]`).getByTitle("Remove").click();
    await expect(page.getByText(REPO)).not.toBeVisible();
  });
});
