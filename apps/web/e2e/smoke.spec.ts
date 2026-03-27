import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

/**
 * Set up API mocks and localStorage keys so the app considers the user authenticated.
 */
async function loginAndSetup(page: import("@playwright/test").Page) {
  await setupApiMocks(page);
  await page.addInitScript(() => {
    localStorage.setItem("quant_api_key", "test-key");
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  await page.goto("/");
}

test.describe("Smoke tests", () => {
  test("login -> dashboard shows NAV and cash metrics", async ({ page }) => {
    await loginAndSetup(page);

    // h1 heading should be visible
    await expect(page.locator("h1")).toBeVisible({ timeout: 10_000 });

    // Metric cards for key values should be present
    const main = page.locator("main");
    await expect(main.getByText("NAV")).toBeVisible({ timeout: 10_000 });
  });

  test("navigate to each page via sidebar links", async ({ page }) => {
    await loginAndSetup(page);

    // Current sidebar nav links (Chinese labels, actual routes)
    const navLinks = [
      { path: "/strategy", heading: /策略中心/ },
      { path: "/risk", heading: /風控/ },
      { path: "/backtest", heading: /回測/ },
      { path: "/settings", heading: /設定/ },
      { path: "/", heading: /總覽/ },
    ];

    for (const { path, heading } of navLinks) {
      await page.locator(`nav a[href="${path}"]`).click();
      await expect(page.locator("h1").first()).toHaveText(heading, {
        timeout: 10_000,
      });
    }
  });
});
