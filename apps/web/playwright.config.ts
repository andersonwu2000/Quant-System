import { defineConfig } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: isCI ? 60_000 : 30_000,
  fullyParallel: true,
  retries: isCI ? 2 : 0,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: isCI ? "http://localhost:4173" : "http://localhost:3000",
    trace: "on-first-retry",
    actionTimeout: isCI ? 15_000 : 10_000,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  webServer: {
    command: isCI ? "bun run build && bun run preview" : "bun run dev",
    port: isCI ? 4173 : 3000,
    reuseExistingServer: !isCI,
    timeout: isCI ? 120_000 : 60_000,
  },
});
