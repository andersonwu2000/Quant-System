import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

async function loginAndSetup(page: import("@playwright/test").Page) {
  await setupApiMocks(page);
  await page.addInitScript(() => {
    localStorage.setItem("quant_api_key", "test-key");
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  await page.goto("/backtest");
}

test.describe("Backtest page", () => {
  test("fill form -> submit -> see metric cards with results", async ({
    page,
  }) => {
    await loginAndSetup(page);

    // Page heading (h1, Chinese)
    await expect(page.locator("h1").first()).toHaveText(/回測/, {
      timeout: 10_000,
    });

    // Set dates via date inputs
    const startInput = page.locator('input[type="date"]').first();
    await startInput.fill("2023-01-01");

    const endInput = page.locator('input[type="date"]').nth(1);
    await endInput.fill("2024-01-01");

    // Click the submit button
    await page.locator("button", { hasText: /執行回測/ }).click();

    // Wait for results — metric cards should appear
    const main = page.locator("main");
    await expect(main.getByText(/Sharpe/i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
