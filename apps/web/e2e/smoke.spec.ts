import { test, expect } from "@playwright/test";
import { setupApiMocks } from "./mocks/handlers";

/**
 * Set up API mocks and localStorage keys so the app considers the user authenticated.
 * Uses page.addInitScript to set localStorage before any app code runs,
 * then sets up Playwright route mocks for all API endpoints.
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
  test("login → dashboard shows NAV, Cash, Positions metrics", async ({
    page,
  }) => {
    await loginAndSetup(page);

    // Dashboard heading should be visible
    await expect(page.locator("h2")).toBeVisible({ timeout: 10_000 });

    // Metric cards for key values should be present
    const main = page.locator("main");
    await expect(main.getByText("NAV")).toBeVisible({ timeout: 10_000 });
    await expect(main.getByText("現金")).toBeVisible();
  });

  test("navigate to each page via sidebar links", async ({ page }) => {
    await loginAndSetup(page);

    // Only routes that exist as sidebar NavLinks are tested here.
    // /portfolio, /orders, /backtest are legacy paths that redirect to /trading or /research
    // and are NOT present as nav links in the current sidebar.
    const navLinks = [
      // /trading shows TradingPage which renders PortfolioPage (h2 "Portfolio") by default
      { path: "/trading",    heading: /portfolio/i },
      { path: "/strategies", heading: /strateg/i },
      { path: "/risk",       heading: /risk/i },
      { path: "/settings",   heading: /setting/i },
    ];

    for (const { path, heading } of navLinks) {
      await page.locator(`nav a[href="${path}"]`).click();
      await expect(page.locator("h2").first()).toHaveText(heading, {
        timeout: 10_000,
      });
    }
  });

  test("logout redirects to settings (login) page", async ({ page }) => {
    await loginAndSetup(page);

    // Click the logout button
    const logoutButton = page.locator("aside button").filter({ has: page.locator("svg") }).first();
    // The logout button contains a LogOut icon — find it by its position (before the collapse toggle)
    const buttons = page.locator("aside > div:last-child button");
    const logoutBtn = buttons.first();
    await logoutBtn.click();

    // After logout the app should redirect to /settings since isAuthenticated() is false
    await expect(page).toHaveURL(/settings/, { timeout: 10_000 });
  });
});
