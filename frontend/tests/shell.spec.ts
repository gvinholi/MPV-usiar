import { expect, test, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByRole("link", { name: "Preparar acesso seguro" }).click();
  const submission = page.waitForResponse(r => r.url().endsWith("/auth/login") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Entrar com sua organização" }).click();
  const response = await submission;
  const headers = response.request().headers();
  expect(response.status(), JSON.stringify({ origin: headers.origin, site: headers["sec-fetch-site"], type: headers["content-type"] })).toBe(303);
  await expect(page).toHaveURL(/\/dashboard$/);
}
test.beforeEach(async ({ request }) => { await request.post("http://127.0.0.1:8100/scenario", { data: "reader" }); });
test("all operational routes require a session; no public BFF proxy exists", async ({ page, request }) => {
  for (const path of ["/dashboard", "/opportunities", "/review-queue", "/collection-rounds"]) {
    await page.goto(path); await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Seu espaço de análise" })).toBeVisible();
  }
  expect((await request.get("/api/v1/opportunities")).status()).toBe(404);
  expect((await request.get("/auth/logout")).status()).toBe(405);
});
test("OIDC login, responsive navigation and logout keep credentials server-side", async ({ page, context, isMobile }) => {
  const leaked: string[] = [];
  page.on("console", msg => { if (/test-only-secret|test-access-marker|access_token|id_token/.test(msg.text())) leaked.push(msg.text()); });
  await login(page);
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await expect(page.getByText("Área em preparação")).toBeVisible();
  const cookies = await context.cookies("http://127.0.0.1:3100");
  const session = cookies.find(c => c.name === "usiar-session");
  expect(session).toMatchObject({ httpOnly: true, sameSite: "Lax", secure: false });
  expect(session?.value).toMatch(/^[A-Za-z0-9_-]{43}$/);
  expect(cookies.find(c => c.name === "usiar-login")).toBeUndefined();
  expect(await page.evaluate(() => document.cookie)).not.toContain("usiar-session");
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  expect(await page.content()).not.toMatch(/test-only-secret|test-access-marker|access_token|id_token|Bearer /);
  expect(await page.content()).not.toMatch(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
  await page.screenshot({ path: `test-results/shell-${isMobile ? "mobile" : "desktop"}.png`, fullPage: true, caret: "initial" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const title of ["Oportunidades", "Fila de Revisão", "Rodadas de Coleta", "Dashboard"]) {
    if (isMobile) await page.getByRole("button", { name: "Abrir menu" }).click();
    await page.getByRole("link", { name: title, exact: true }).filter({ visible: true }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    if (isMobile) await expect(page.getByRole("dialog")).not.toBeVisible();
  }
  if (isMobile) {
    await page.getByRole("button", { name: "Abrir menu" }).click();
    await page.keyboard.press("Escape"); await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Abrir menu" })).toBeFocused();
  }
  const response = await page.request.get("/dashboard");
  expect(response.headers()["cache-control"]).toContain("no-store");
  await page.getByRole("button", { name: "Sair", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await context.addCookies([session!]);
  await page.goto("/dashboard"); await expect(page).toHaveURL(/\/login$/);
  expect(leaked).toEqual([]);
});
test("rejects CSRF for logout and login without ending the valid session", async ({ page }) => {
  await login(page);
  const csrf = await page.locator('input[name="csrf"]').inputValue();
  const response = await page.request.post("/auth/logout", { headers: { Origin: "https://evil.test" }, form: { csrf } });
  expect(response.status()).toBe(403);
  const missing = await page.request.post("/auth/logout", { headers: { Origin: "http://127.0.0.1:3100" }, form: { csrf: "wrong" } });
  expect(missing.status()).toBe(403);
  await page.goto("/dashboard"); await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  const start = await page.request.post("/auth/login", { headers: { Origin: "https://evil.test" }, form: { csrf } });
  expect(start.status()).toBe(403);
});
test("reviews:write alone does not authorize dashboard data", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8100/scenario", { data: "writer" });
  await login(page);
  await expect(page.getByRole("alert").filter({ hasText: "Consulta indisponível" })).toContainText("Você não tem permissão");
  await expect(page.getByText("Área em preparação")).not.toBeVisible();
});
test("callback failures use a configured redirect and sanitized message", async ({ page, request }) => {
  const response = await request.get("/auth/callback?code=sensitive-test-code&state=wrong", { maxRedirects: 0, headers: { Host: "attacker.test", "X-Forwarded-Host": "attacker.test" } });
  expect(response.headers().location).toBe("http://127.0.0.1:3100/login?error=authentication");
  expect(await response.text()).not.toContain("sensitive-test-code");
  await page.goto("/login?error=authentication"); await expect(page.getByRole("alert").filter({ hasText: "Não foi possível concluir" })).toBeVisible();
});
