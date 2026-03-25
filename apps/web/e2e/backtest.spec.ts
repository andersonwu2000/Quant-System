import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

async function loginAndSetup(page: import("@playwright/test").Page) {
  await setupApiMocks(page);
  await page.addInitScript(() => {
    localStorage.setItem("quant_api_key", "test-key");
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  // /backtest redirects to /research, which defaults to Backtest tab
  await page.goto("/research");
}

test.describe("Backtest page", () => {
  test("fill form → submit → see metric cards with results", async ({
    page,
  }) => {
    await loginAndSetup(page);

    // Page heading
    await expect(page.locator("h2").first()).toHaveText(/backtest/i, {
      timeout: 10_000,
    });

    // The form should be visible
    const form = page.locator("form");
    await expect(form).toBeVisible({ timeout: 5_000 });

    // Universe is pre-filled via UniversePicker; just set dates
    const startInput = form.locator('input[type="date"]').first();
    await startInput.fill("2023-01-01");

    const endInput = form.locator('input[type="date"]').nth(1);
    await endInput.fill("2024-01-01");

    // Submit the backtest
    await form.locator('button[type="submit"]').click();

    // Wait for results — metric cards should appear with backtest results
    // The mock returns total_return: 0.234, sharpe: 1.85, etc.
    // MetricCard renders the values; look for the metric labels
    const main = page.locator("main");
    await expect(main.getByText(/total return/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(main.getByText(/sharpe/i)).toBeVisible();
    await expect(main.getByText(/max drawdown/i)).toBeVisible();
  });
});
