import { defineConfig, devices } from "@playwright/test";

// Tests de bout en bout contre le déploiement complet (deploy/docker-compose.yml).
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 240_000,
  expect: { timeout: 20_000 },
  workers: 1, // le Hub limite le nombre de serveurs : pas de parallélisme
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "https://localhost",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    viewport: { width: 1400, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1400, height: 900 },
        launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
      },
    },
  ],
});
