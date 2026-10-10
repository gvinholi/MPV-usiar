import { defineConfig, devices } from "@playwright/test";

const webServer = process.env.PLAYWRIGHT_EXTERNAL_SERVERS === "1" ? undefined : [
  { command: "node tests/fixtures/server.mjs", url: "http://127.0.0.1:8100/health", reuseExistingServer: false, timeout: 60000 },
  { command: "node tests/fixtures/next-server.mjs 3300", url: "http://127.0.0.1:3300/auth/callback", reuseExistingServer: false, timeout: 120000,
    env: { AUTH_MODE: "internal", AUTH_COOKIE_KEY: "A".repeat(43), APP_ORIGIN: "http://127.0.0.1:3300",
      FASTAPI_BASE_URL: "http://127.0.0.1:8100", API_PROFILE_ID: "", API_PROFILE_CODE: "USIAR",
      NEXT_TELEMETRY_DISABLED: "1" },
  },
];

export default defineConfig({
  testDir: "./tests",
  testMatch: "internal-auth.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: { baseURL: "http://127.0.0.1:3300", trace: "off" },
  projects: [
    { name: "internal-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "internal-mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" } },
  ],
  webServer,
});
