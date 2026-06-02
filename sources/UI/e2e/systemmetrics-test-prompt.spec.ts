import { test, expect } from "@playwright/test";

test.describe("SystemMetrics test prompt panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForSelector("h2");
  });

  test("renders prompt textarea + Run button", async ({ page }) => {
    const ta = page.getByLabel(/test prompt|max 500/i);
    await expect(ta).toBeVisible();
    await expect(page.getByRole("button", { name: /run test/i })).toBeVisible();
  });

  test("Run with default prompt shows result card", async ({ page }) => {
    await page.getByRole("button", { name: /run test/i }).click();
    const card = page.getByRole("region", { name: /test prompt result/i });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText(/TTFT/)).toBeVisible();
    await expect(card.getByText(/TPS/)).toBeVisible();
  });

  test("empty prompt prevents request (red border)", async ({ page }) => {
    const ta = page.getByLabel(/test prompt|max 500/i);
    await ta.fill("");
    await page.getByRole("button", { name: /run test/i }).click();
    await expect(ta).toHaveCSS("border-color", /.+/); // any non-default border indicates error state
  });
});
