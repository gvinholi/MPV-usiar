// Windows-safe orchestration for the isolated internal-auth browser suite.
import { spawn } from "node:child_process";

const root = process.cwd();
const inherited = { ...process.env };
// The surrounding developer environment may use DEBUG for unrelated tooling.
// Next interprets any DEBUG value as its private Turbopack test mode, which
// causes continuous browser refreshes while Playwright is running.
delete inherited.DEBUG;
const nextEnvironment = {
  ...inherited,
  AUTH_MODE: "internal",
  AUTH_COOKIE_KEY: "A".repeat(43),
  APP_ORIGIN: "http://127.0.0.1:3300",
  FASTAPI_BASE_URL: "http://127.0.0.1:8100",
  API_PROFILE_ID: "42227c23-f6ea-5a43-b640-56ed6eb6981c",
  API_PROFILE_CODE: "",
  NEXT_TELEMETRY_DISABLED: "1",
};

const children = [];
function launch(args, env = inherited) {
  const child = spawn(process.execPath, args, { cwd: root, env, stdio: "inherit", windowsHide: true });
  children.push(child);
  return child;
}

async function waitFor(url, accepted, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { redirect: "manual" });
      if (accepted(response.status)) return;
    } catch { /* Server is still starting. */ }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error(`Test server did not become ready: ${url}`);
}

async function stop(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGINT");
  await Promise.race([
    new Promise(resolve => child.once("exit", resolve)),
    new Promise(resolve => setTimeout(resolve, 3000)),
  ]);
  if (child.exitCode === null && child.signalCode === null) child.kill();
}

let exitCode = 1;
try {
  launch(["tests/fixtures/server.mjs"]);
  // The fixture writes its public test CA during startup. Finish that write
  // before Next starts watching the workspace for development changes.
  await waitFor("http://127.0.0.1:8100/health", status => status === 200, 60_000);
  launch(["tests/fixtures/next-server.mjs", "3300"], nextEnvironment);
  await waitFor("http://127.0.0.1:3300/auth/callback", status => status === 403, 120_000);
  const runner = launch([
    "node_modules/@playwright/test/cli.js", "test", "--config", "playwright.internal.config.ts",
    ...process.argv.slice(2),
  ], { ...inherited, PLAYWRIGHT_EXTERNAL_SERVERS: "1" });
  exitCode = await new Promise(resolve => runner.once("exit", code => resolve(code ?? 1)));
} finally {
  for (const child of children.reverse()) await stop(child);
}
process.exit(exitCode);
