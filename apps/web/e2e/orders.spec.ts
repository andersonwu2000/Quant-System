import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

async function loginAndSetup(page: import("@playwright/test").Page) {
  await setupApiMocks(page);
  await page.addInitScript(() => {
    localStorage.setItem("quant_api_key", "test-key");
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  // /orders redirects to /trading which defaults to Portfolio tab
  // Navigate to /trading, then click Orders tab
  await page.goto("/trading");
}

test.describe("Orders page", () => {
  test("navigate to orders tab → see order table", async ({ page }) => {
    await loginAndSetup(page);

    // TradingPage defaults to Portfolio tab; click Orders tab
    const ordersTab = page.locator("button", { hasText: /order/i });
    await ordersTab.click();

    // Page heading inside Orders tab
    await expect(page.locator("h2")).toHaveText(/order/i, { timeout: 10_000 });

    // Table should be visible with header columns
    const table = page.locator("table");
    await expect(table).toBeVisible({ timeout: 10_000 });

    // Verify some order data rendered (symbol from mock)
    await expect(page.getByText("AAPL")).toBeVisible();
  });

  test("fill order form → submit → success toast appears", async ({
    page,
  }) => {
    await loginAndSetup(page);

    // Switch to Orders tab first
    const ordersTab = page.locator("button", { hasText: /order/i });
    await ordersTab.click();
    await expect(page.locator("h2")).toHaveText(/order/i, { timeout: 10_000 });

    // Open the order form — click "New Order" button
    const newOrderBtn = page.locator("button", { hasText: /new order/i });
    await newOrderBtn.click();

    // Fill the form
    const form = page.locator('form[aria-label="New order form"]');
    await expect(form).toBeVisible({ timeout: 5_000 });

    // Symbol input
    await form.locator('input[placeholder="AAPL"]').fill("TSLA");

    // Quantity input (type=number)
    const qtyInput = form.locator('input[type="number"]').first();
    await qtyInput.fill("50");

    // Price input (type=number, second one)
    const priceInput = form.locator('input[type="number"]').nth(1);
    await priceInput.fill("250");

    // Submit — opens confirmation dialog
    await form.locator('button[type="submit"]').click();

    // Click Confirm in the confirmation dialog
    const confirmBtn = page.locator("button", { hasText: /confirm/i });
    await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
    await confirmBtn.click();

    // Toast notification should appear
    await expect(page.getByText(/order submitted|success/i)).toBeVisible({
      timeout: 10_000,
    });
  });
});
