// Windows-safe orchestration for the OIDC regression browser suite.
import { spawn } from "node:child_process";
import { resolve } from "node:path";

const root = process.cwd();
const inherited = { ...process.env };
// Do not let an unrelated DEBUG setting enable Next's private test mode.
delete inherited.DEBUG;
const oidcEnvironment = {
  ...inherited, AUTH_MODE: "oidc", APP_ORIGIN: "http://127.0.0.1:3100", FASTAPI_BASE_URL: "http://127.0.0.1:8100",
  OIDC_ISSUER: "https://127.0.0.1:4443", OIDC_CLIENT_ID: "test-client", OIDC_CLIENT_SECRET: "test-only-secret",
  OIDC_CLIENT_AUTH_METHOD: "client_secret_basic", OIDC_SCOPES: "openid dashboard:read", OIDC_ID_TOKEN_ALG: "RS256",
  OIDC_RESOURCE: "", OIDC_AUDIENCE: "", API_PROFILE_ID: "", API_PROFILE_CODE: "USIAR",
  NODE_EXTRA_CA_CERTS: resolve(".test-tls/ca.pem"), NEXT_TELEMETRY_DISABLED: "1",
};
const productionEnvironment = {
  ...inherited, NODE_ENV: "production", AUTH_MODE: "oidc", APP_ORIGIN: "https://app.test", FASTAPI_BASE_URL: "https://api.test",
  OIDC_ISSUER: "https://issuer.test", OIDC_CLIENT_ID: "test-client", OIDC_CLIENT_AUTH_METHOD: "none", OIDC_CLIENT_SECRET: "",
  OIDC_SCOPES: "openid dashboard:read", OIDC_RESOURCE: "", OIDC_AUDIENCE: "", OIDC_ID_TOKEN_ALG: "RS256",
  API_PROFILE_ID: "", API_PROFILE_CODE: "", NEXT_TELEMETRY_DISABLED: "1",
};

const children = [];
function launch(args, env = inherited) {
  const child = spawn(process.execPath, args, { cwd: root, env, stdio: "inherit", windowsHide: true });
  children.push(child); return child;
}
async function waitFor(url, accepted, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try { const response = await fetch(url, { redirect: "manual" }); if (accepted(response.status)) return; }
    catch { /* Server is still starting. */ }
    await new Promise(resolveDelay => setTimeout(resolveDelay, 200));
  }
  throw new Error(`Test server did not become ready: ${url}`);
}
async function stop(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGINT");
  await Promise.race([new Promise(resolveExit => child.once("exit", resolveExit)), new Promise(resolveDelay => setTimeout(resolveDelay, 3000))]);
  if (child.exitCode === null && child.signalCode === null) child.kill();
}

let exitCode = 1;
try {
  launch(["tests/fixtures/server.mjs"]);
  // The fixture creates the public test CA consumed by the OIDC client.
  await waitFor("http://127.0.0.1:8100/health", status => status === 200, 60_000);
  launch(["tests/fixtures/next-server.mjs", "3100"], oidcEnvironment);
  launch(["tests/fixtures/next-server.mjs", "3200", "production"], productionEnvironment);
  await Promise.all([
    waitFor("http://127.0.0.1:3100/login", status => status === 200, 120_000),
    waitFor("http://127.0.0.1:3200/login", status => status === 200, 60_000),
  ]);
  const runner = launch(["node_modules/@playwright/test/cli.js", "test", "--config", "playwright.config.ts", ...process.argv.slice(2)],
    { ...inherited, PLAYWRIGHT_EXTERNAL_SERVERS: "1" });
  exitCode = await new Promise(resolveExit => runner.once("exit", code => resolveExit(code ?? 1)));
} finally {
  for (const child of children.reverse()) await stop(child);
}
process.exit(exitCode);
