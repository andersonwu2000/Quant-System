import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

async function loginAndSetup(page: import("@playwright/test").Page) {
  await setupApiMocks(page);
  await page.addInitScript(() => {
    localStorage.setItem("quant_api_key", "test-key");
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  // Overview page shows positions including order-related data
  await page.goto("/");
}

test.describe("Overview page — positions and data", () => {
  test("dashboard loads and shows position data", async ({ page }) => {
    await loginAndSetup(page);

    // Page heading
    await expect(page.locator("h1").first()).toHaveText(/總覽/, {
      timeout: 10_000,
    });

    // Positions section heading
    await expect(page.getByText("持倉明細")).toBeVisible({ timeout: 10_000 });

    // Verify position data rendered from mock (symbols)
    await expect(page.getByText("AAPL")).toBeVisible({ timeout: 10_000 });
  });
});
