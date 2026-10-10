import { defineConfig, devices, type PlaywrightTestConfig } from "@playwright/test";
import { resolve } from "node:path";

const webServer: PlaywrightTestConfig["webServer"] = process.env.PLAYWRIGHT_EXTERNAL_SERVERS === "1" ? undefined : [
  { command: "node tests/fixtures/server.mjs", url: "http://127.0.0.1:8100/health", reuseExistingServer: false, timeout: 60000 },
  { command: "npm run dev -- --port 3100", url: "http://127.0.0.1:3100/login", reuseExistingServer: false, timeout: 120000,
    env: { AUTH_MODE: "oidc", APP_ORIGIN: "http://127.0.0.1:3100", FASTAPI_BASE_URL: "http://127.0.0.1:8100", OIDC_ISSUER: "https://127.0.0.1:4443",
      OIDC_CLIENT_ID: "test-client", OIDC_CLIENT_SECRET: "test-only-secret", OIDC_CLIENT_AUTH_METHOD: "client_secret_basic",
      OIDC_SCOPES: "openid dashboard:read", OIDC_ID_TOKEN_ALG: "RS256", OIDC_RESOURCE: "", OIDC_AUDIENCE: "",
      API_PROFILE_ID: "", API_PROFILE_CODE: "USIAR", NODE_EXTRA_CA_CERTS: resolve(".test-tls/ca.pem"), NEXT_TELEMETRY_DISABLED: "1" },
  },
  { command: "npm run start -- --port 3200", url: "http://127.0.0.1:3200/login", reuseExistingServer: false, timeout: 60000,
    env: { NODE_ENV: "production", AUTH_MODE: "oidc", APP_ORIGIN: "https://app.test", FASTAPI_BASE_URL: "https://api.test",
      OIDC_ISSUER: "https://issuer.test", OIDC_CLIENT_ID: "test-client", OIDC_CLIENT_AUTH_METHOD: "none", OIDC_CLIENT_SECRET: "",
      OIDC_SCOPES: "openid dashboard:read", OIDC_RESOURCE: "", OIDC_AUDIENCE: "", OIDC_ID_TOKEN_ALG: "RS256",
      API_PROFILE_ID: "", API_PROFILE_CODE: "", NEXT_TELEMETRY_DISABLED: "1" },
  },
];

export default defineConfig({
  testDir: "./tests", testMatch: "*.spec.ts", fullyParallel: false, workers: 1,
  testIgnore: "internal-auth.spec.ts",
  timeout: 60000, expect: { timeout: 15000 },
  use: { baseURL: "http://127.0.0.1:3100", ignoreHTTPSErrors: true, trace: "off" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" } },
  ],
  webServer,
});
