import { describe, expect, it } from "vitest";
import { MemorySessionStore } from "../src/lib/server/auth/session-store";
import { cookieSettings, createAuthService } from "../src/lib/server/auth/session";
import { verifyCsrf } from "../src/lib/server/auth/csrf";
import { oidcEnv, testEnv } from "./helpers";

describe("sessions and login transactions", () => {
  it("expires on inactivity and absolute/token deadline", async () => {
    let now = 1000; const store = new MemorySessionStore(100, () => now, "test");
    const id = await store.createSession({ accessToken: "secret", subject: "user", csrf: "csrf", createdAt: now, lastSeenAt: now, expiresAt: 1250 });
    now = 1099; expect(await store.readSession(id)).toBeDefined();
    now = 1198; expect(await store.readSession(id)).toBeDefined();
    now = 1250; expect(await store.readSession(id)).toBeUndefined();
    now = 2000;
    const idle = await store.createSession({ accessToken: "secret", subject: "user", csrf: "csrf", createdAt: now, lastSeenAt: now, expiresAt: 3000 });
    now = 2100; expect(await store.readSession(idle)).toBeUndefined();
  });
  it("consumes transactions atomically and expires them", async () => {
    let now = 1000; const store = new MemorySessionStore(100, () => now, "test");
    const id = await store.createTransaction({ csrf: "csrf", expiresAt: 1100 });
    const results = await Promise.all([store.consumeTransaction(id), store.consumeTransaction(id)]);
    expect(results.filter(Boolean)).toHaveLength(1);
    const expired = await store.createTransaction({ csrf: "csrf", expiresAt: 1100 });
    now = 1100; expect(await store.consumeTransaction(expired)).toBeUndefined();
  });
  it("logout invalidation is effective and identifiers are opaque", async () => {
    const store = new MemorySessionStore(1000, Date.now, "test");
    const id = await store.createSession({ accessToken: "sensitive", subject: "sensitive-user", csrf: "csrf", createdAt: Date.now(), lastSeenAt: Date.now(), expiresAt: Date.now() + 5000 });
    expect(id).toMatch(/^[A-Za-z0-9_-]{43}$/); expect(id).not.toContain("sensitive");
    await store.deleteSession(id); expect(await store.readSession(id)).toBeUndefined();
  });
  it("applies cookie flags and __Host- only with secure production settings", () => {
    const dev = cookieSettings(testEnv(), "session", 300);
    expect(dev).toMatchObject({ httpOnly: true, secure: false, sameSite: "lax", path: "/", maxAge: 300 });
    const prod = cookieSettings(testEnv({ NODE_ENV: "production", APP_ORIGIN: "https://app.test", FASTAPI_BASE_URL: "https://api.test" }), "session", 300);
    expect(prod.name).toBe("__Host-usiar-session"); expect(prod.secure).toBe(true); expect(prod).not.toHaveProperty("domain");
  });
  it("prelogin transactions are short-lived and reveal only CSRF", async () => {
    const env = oidcEnv(); const store = new MemorySessionStore(1000, () => 0, "test");
    const auth = createAuthService(env, store, undefined, () => 0);
    const login = await auth.prepareLogin();
    expect(await store.readTransaction(login.id)).toEqual({ csrf: login.csrf, expiresAt: 300000 });
  });
});

describe("CSRF", () => {
  const request = (headers: Record<string, string> = {}, body = "csrf=expected") => new Request("http://127.0.0.1:3000/auth/logout", {
    method: "POST", headers: { Origin: "http://127.0.0.1:3000", "Content-Type": "application/x-www-form-urlencoded", ...headers }, body,
  });
  it("accepts same-origin POST with a session-bound token", async () => {
    await expect(verifyCsrf(request(), "http://127.0.0.1:3000", "expected")).resolves.toBeUndefined();
  });
  it.each([
    [{ Origin: "https://evil.test" }, "csrf=expected"], [{ Origin: "" }, "csrf=expected"], [{ Origin: "null" }, "csrf=expected"],
    [{ "Sec-Fetch-Site": "cross-site" }, "csrf=expected"], [{ "Content-Type": "application/json" }, "csrf=expected"],
    [{}, "csrf=wrong"], [{}, ""], [{}, "csrf=expected&csrf=expected"], [{}, "csrf=" + "x".repeat(3000)],
  ] as [Record<string, string>, string][])("rejects forged requests", async (headers, body) => {
    await expect(verifyCsrf(request(headers, body), "http://127.0.0.1:3000", "expected")).rejects.toThrow("Solicitação não autorizada");
  });
  it("rejects GET mutations", async () => {
    await expect(verifyCsrf(new Request("http://127.0.0.1:3000/auth/logout"), "http://127.0.0.1:3000", "expected")).rejects.toThrow();
  });
});
