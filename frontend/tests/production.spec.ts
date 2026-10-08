import { expect, test } from "@playwright/test";

test("production stays closed even with complete OIDC configuration", async ({ request, page }) => {
  const base = "http://127.0.0.1:3200";
  for (const path of ["/auth/login", "/auth/callback?code=never-exchange&state=untrusted"]) {
    const result = await request.get(base + path, { maxRedirects: 0 });
    expect(result.status()).toBe(503);
    expect(await result.json()).toEqual({ error: "Autenticação indisponível." });
    expect(result.headers()["set-cookie"]).toBeUndefined();
  }
  await page.goto(base + "/dashboard");
  await expect(page).toHaveURL(base + "/login");
  await expect(page.getByRole("status")).toContainText("Autenticação indisponível");
  await expect(page.getByRole("button", { name: "Entrar com sua organização" })).not.toBeVisible();
});
