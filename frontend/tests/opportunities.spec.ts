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

test("renders the 12 UsiAr columns, real mappings and safe links responsively", async ({ page }) => {
  await login(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: "Oportunidades", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader").allTextContents()).resolves.toEqual([
    "ID RHS", "DATA", "Hr", "ORGÃO", "CIDADE", "TIPO", "SITE", "N EDITAL",
    "TIPO DO SERVIÇO", "VALOR MENSAL", "VALOR ESTIMADO", "OBSERVAÇÃO",
  ]);
  await expect(page.getByRole("cell", { name: "Universidade Pública" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "13/10/2026" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "09" })).toBeVisible();
  await expect(page.getByText("R$ 1.234,56")).toBeVisible();
  await expect(page.getByText("CANDIDATE", { exact: true })).toBeVisible();
  await expect(page.getByText("PENDING", { exact: true })).toBeVisible();
  const official = page.getByRole("link", { name: "Abrir edital" });
  await expect(official).toHaveAttribute("href", "https://pncp.gov.br/app/editais/exemplo");
  await expect(official).toHaveAttribute("target", "_blank");
  await expect(official).toHaveAttribute("rel", "noopener noreferrer");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.content()).not.toMatch(/test-access-marker|Bearer |access_token|session_token|csrf_token/);
});

test("uses server pagination, resets the page on filters and shows route loading", async ({ page, request }) => {
  await login(page);
  await page.goto("/opportunities");
  await expect(page.getByText("26 resultados")).toBeVisible();
  await page.getByRole("link", { name: "Próxima" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("page")).toBe("2");
  await expect(page.getByRole("cell", { name: "Instituto Federal" })).toBeVisible();

  await page.getByRole("link", { name: "Somente pendentes" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("state")).toBe("pending");
  expect(new URL(page.url()).searchParams.has("page")).toBe(false);
  await expect(page.getByText("PENDING", { exact: true })).toBeVisible();
  await expect(page.getByText("CANDIDATE", { exact: true })).toHaveCount(0);

  await request.post("http://127.0.0.1:8100/scenario", { data: "slow-opportunities" });
  const navigation = page.goto("/opportunities?state=candidate");
  await expect(page.getByRole("status", { name: "Carregando oportunidades" })).toBeVisible();
  await navigation;
  await expect(page.getByText("CANDIDATE", { exact: true })).toBeVisible();
});

test("distinguishes empty data, recoverable errors and an expired session", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8100/scenario", { data: "empty" });
  await login(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("status").filter({ hasText: "Nenhuma oportunidade coletada" })).toContainText("primeira coleta");

  await request.post("http://127.0.0.1:8100/scenario", { data: "opportunities-error" });
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Não foi possível consultar oportunidades" })).toContainText("temporariamente indisponível");
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  expect(await page.content()).not.toMatch(/test-access-marker|TEST_SECRET/);

  await request.post("http://127.0.0.1:8100/scenario", { data: "opportunities-expired" });
  await page.reload();
  await expect(page).toHaveURL(/\/login\?error=session$/);
  await expect(page.getByText("Sua sessão expirou ou foi encerrada")).toBeVisible();
});
