import { expect, test, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByRole("link", { name: "Preparar acesso seguro" }).click();
  await page.getByRole("button", { name: "Entrar com sua organização" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8100/scenario", { data: "reader" });
});

test("renders the real summary contract and an unknown source responsively", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Dashboard operacional" })).toBeVisible();
  await expect(page.getByText("Código USIAR")).toBeVisible();
  await expect(page.getByText("c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4")).toBeVisible();
  for (const section of ["Indicadores principais", "Situação atual da coorte", "Funil de oportunidades", "Atividade no período", "Cobertura por fonte"]) {
    await expect(page.getByRole("heading", { name: section })).toBeVisible();
  }
  await expect(page.getByRole("rowheader", { name: "FONTE-NOVA" })).toBeVisible();
  await expect(page.getByRole("table")).toHaveAccessibleName("Cobertura geral da coleta agrupada por fonte");
  await expect(page.getByText("Métricas gerais da coleta no período, sem restrição ao perfil consultado.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel("Início").focus();
  await expect(page.getByLabel("Início")).toBeFocused();
});

test("converts local period limits to UTC, preserves them in the URL and clears them", async ({ page }) => {
  await login(page);
  await page.getByLabel("Início").fill("2026-10-01T09:30");
  await page.getByLabel("Fim exclusivo").fill("2026-10-02T10:45");
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("from_datetime")).toMatch(/Z$/);
  const filtered = new URL(page.url());
  expect(Date.parse(filtered.searchParams.get("from_datetime")!)).toBeLessThan(Date.parse(filtered.searchParams.get("to_datetime")!));
  await expect(page.getByText("Horários exibidos em UTC; o limite final é exclusivo.")).toBeVisible();
  await page.getByRole("button", { name: "Limpar" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("rejects inverted, repeated and unknown period parameters", async ({ page }) => {
  await login(page);
  await page.getByLabel("Início").fill("2026-10-02T10:00");
  await page.getByLabel("Fim exclusivo").fill("2026-10-01T10:00");
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "O início deve ser anterior ao fim." })).toBeVisible();

  await page.goto("/dashboard?from_datetime=2026-10-01T00%3A00%3A00Z&from_datetime=2026-10-02T00%3A00%3A00Z");
  await expect(page.getByRole("alert").filter({ hasText: "Período inválido" })).toBeVisible();
  await page.goto("/dashboard?profile_id=c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4");
  await expect(page.getByRole("alert").filter({ hasText: "Período inválido" })).toBeVisible();
});

test("distinguishes a real empty summary from service errors", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8100/scenario", { data: "empty" });
  await login(page);
  await expect(page.getByRole("status").filter({ hasText: "Nenhum dado no período" })).toBeVisible();

  await request.post("http://127.0.0.1:8100/scenario", { data: "error-409" });
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Consulta indisponível" })).toContainText("Configure API_PROFILE_ID");

  await request.post("http://127.0.0.1:8100/scenario", { data: "error-503" });
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Consulta indisponível" })).toContainText("temporariamente indisponível");
  expect(await page.content()).not.toMatch(/test-access-marker|Bearer |access_token|id_token/);
});
