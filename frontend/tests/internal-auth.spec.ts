import { expect, test, type Page } from "@playwright/test";

const password = "senha interna válida 🔐";

async function selectScenario(page: Page, scenario: string) {
  await page.request.post("http://127.0.0.1:8100/scenario", { data: scenario });
}

async function login(page: Page) {
  await page.goto("/login");
  await expect(page.getByLabel("E-mail")).toBeVisible();
  await page.getByLabel("E-mail").fill("admin@example.com");
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Mostrar senha" }).click();
  await expect(page.getByLabel("Senha", { exact: true })).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Ocultar senha" }).click();
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
}

test.beforeEach(async ({ page }) => { await selectScenario(page, "reader"); });

test("internal login, responsive dashboard and logout keep FastAPI secrets out of the browser", async ({ page, context }) => {
  const leaked: string[] = [];
  page.on("console", message => { if (/usiar_s1|csrf_token|session_token|senha interna/i.test(message.text())) leaked.push(message.text()); });
  await login(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard operacional", exact: true })).toBeVisible();
  const cookies = await context.cookies("http://127.0.0.1:3300");
  const session = cookies.find(cookie => cookie.name === "usiar-internal-session");
  expect(session).toMatchObject({ httpOnly: true, sameSite: "Lax", secure: false, path: "/" });
  expect(session?.value).toMatch(/^v1\./);
  expect(session?.value).not.toContain("usiar_s1");
  expect(await page.evaluate(() => document.cookie)).not.toContain("usiar-internal-session");
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  expect(await page.content()).not.toMatch(/usiar_s1|session_token|csrf_token|Bearer /);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Sair", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await context.cookies()).some(cookie => cookie.name === "usiar-internal-session")).toBe(false);
  await context.addCookies([session!]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?error=session$/);
  expect(leaked).toEqual([]);
});

test("shows generic invalid, throttled and unavailable login states", async ({ page }) => {
  for (const [scenario, message] of ([
    ["auth-invalid", "Verifique suas credenciais"],
    ["auth-rate", "Muitas tentativas"],
    ["auth-unavailable", "temporariamente indisponível"],
  ] as const)) {
    await selectScenario(page, scenario);
    await login(page);
    await expect(page).toHaveURL(new RegExp(`/login\\?error=`));
    await expect(page.getByRole("alert")).toContainText(message);
  }
});

test("rejects forged login and logout requests without destroying a valid session", async ({ page }) => {
  await page.goto("/login");
  const loginCsrf = await page.locator('input[name="csrf"]').inputValue();
  const forgedLogin = await page.request.post("/auth/login", {
    headers: { Origin: "https://evil.test" },
    form: { csrf: loginCsrf, email: "admin@example.com", password },
  });
  expect(forgedLogin.status()).toBe(403);
  await login(page);
  const logoutCsrf = await page.locator('input[name="csrf"]').inputValue();
  const forgedLogout = await page.request.post("/auth/logout", {
    headers: { Origin: "https://evil.test" }, form: { csrf: logoutCsrf },
  });
  expect(forgedLogout.status()).toBe(403);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard operacional", exact: true })).toBeVisible();
});

test("rejects tampered cookies and preserves authorization at FastAPI", async ({ page, context }) => {
  await login(page);
  const cookies = await context.cookies("http://127.0.0.1:3300");
  const session = cookies.find(cookie => cookie.name === "usiar-internal-session")!;
  const parts = session.value.split(".");
  parts[2] = `${parts[2]![0] === "A" ? "B" : "A"}${parts[2]!.slice(1)}`;
  await context.addCookies([{ ...session, value: parts.join(".") }]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?error=session$/);

  await context.clearCookies();
  await selectScenario(page, "writer");
  await login(page);
  await expect(page.getByRole("alert").filter({ hasText: "Consulta indisponível" })).toContainText("Você não tem permissão");
});
