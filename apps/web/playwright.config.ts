import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PDFHUB_E2E_PORT || 3100);
const baseURL = process.env.PDFHUB_E2E_BASE_URL || `http://127.0.0.1:${port}`;
const validationServer = process.env.PDFHUB_E2E_SERVER_MODE === "production"
  ? `rm -rf .next/standalone/public .next/standalone/.next/static && cp -R public .next/standalone/public && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/static && HOSTNAME=127.0.0.1 PORT=${port} node .next/standalone/server.js`
  : `npm run dev -- --hostname 127.0.0.1 --port ${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  workers: process.env.CI ? 1 : undefined,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: process.env.PDFHUB_E2E_BASE_URL ? undefined : {
    command: validationServer,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], browserName: "chromium" },
    },
  ],
});
