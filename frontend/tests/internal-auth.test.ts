import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { createInternalAuthClient } from "../src/lib/server/auth/internal";
import { openInternalSession, sealInternalSession } from "../src/lib/server/auth/sealed-cookie";
import { cookieSettings } from "../src/lib/server/auth/session";
import { logout, startLogin } from "../src/lib/server/auth/http";
import { testEnv } from "./helpers";

const key = Buffer.alloc(32, 7);
const keyText = key.toString("base64url");
const sessionToken = `usiar_s1.9d0ba38f-5905-4f61-a407-31df68c15ddf.${"B".repeat(43)}`;
const apiCsrf = "C".repeat(43);
const browserCsrf = "D".repeat(43);

function response(now = Date.now()) {
  return {
    token_type: "Bearer",
    session_token: sessionToken,
    csrf_token: apiCsrf,
    idle_expires_at: new Date(now + 30 * 60_000).toISOString(),
    absolute_expires_at: new Date(now + 8 * 60 * 60_000).toISOString(),
  };
}

function routeEnvironment() {
  vi.stubEnv("NODE_ENV", "test");
  vi.stubEnv("AUTH_MODE", "internal");
  vi.stubEnv("AUTH_COOKIE_KEY", keyText);
  vi.stubEnv("APP_ORIGIN", "http://127.0.0.1:3000");
  vi.stubEnv("FASTAPI_BASE_URL", "http://127.0.0.1:8000");
}

function post(path: string, body: string, cookie: string) {
  return new NextRequest(`http://127.0.0.1:3000${path}`, {
    method: "POST",
    headers: {
      Origin: "http://127.0.0.1:3000",
      "Sec-Fetch-Site": "same-origin",
      "Content-Type": "application/x-www-form-urlencoded",
      Cookie: cookie,
    },
    body,
  });
}

beforeEach(routeEnvironment);

describe("AES-GCM internal session envelope", () => {
  const payload = { version: 1 as const, mode: "internal" as const, sessionToken, apiCsrf, browserCsrf, absoluteExpiresAt: 20_000 };

  it("round-trips without exposing credentials and uses a fresh IV", () => {
    const first = sealInternalSession(payload, key);
    const second = sealInternalSession(payload, key);
    expect(first).not.toBe(second);
    expect(first).not.toContain(sessionToken);
    expect(first).not.toContain(apiCsrf);
    expect(openInternalSession(first, key, () => 10_000)).toEqual(payload);
  });

  it("rejects tampering, wrong keys, wrong modes, malformed values and expiration", () => {
    const sealed = sealInternalSession(payload, key);
    const parts = sealed.split(".");
    parts[2] = `${parts[2]![0] === "A" ? "B" : "A"}${parts[2]!.slice(1)}`;
    expect(() => openInternalSession(parts.join("."), key, () => 10_000)).toThrow();
    expect(() => openInternalSession(sealed, Buffer.alloc(32, 8), () => 10_000)).toThrow();
    expect(() => openInternalSession(sealed, key, () => 20_000)).toThrow();
    expect(() => openInternalSession("v2.invalid", key)).toThrow();
    expect(() => sealInternalSession({ ...payload, mode: "oidc" } as never, key)).toThrow();
  });
});

describe("internal authentication API client", () => {
  it("posts Unicode credentials only to the configured endpoint with safe fetch options", async () => {
    const env = testEnv();
    const transport = vi.fn(async () => Response.json(response(), { status: 201 }));
    const result = await createInternalAuthClient(env, transport).login({
      email: "administrador+ação@example.com",
      password: "  senha Unicode muito longa 🔐  ",
    });
    expect(result.session_token).toBe(sessionToken);
    const [url, init] = transport.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.href).toBe("http://127.0.0.1:8000/api/v1/auth/session");
    expect(init).toMatchObject({ method: "POST", redirect: "error", cache: "no-store", credentials: "omit" });
    expect(new Headers(init.headers).has("cookie")).toBe(false);
  });

  it.each([
    [401, "INVALID_CREDENTIALS"], [403, "FORBIDDEN"], [422, "INVALID_INPUT"],
    [429, "RATE_LIMITED"], [500, "UNAVAILABLE"], [503, "UNAVAILABLE"],
  ])("sanitizes HTTP %i as %s", async (status, code) => {
    const transport = async () => new Response("upstream secret", { status, headers: status === 429 ? { "Retry-After": "30" } : {} });
    await expect(createInternalAuthClient(testEnv(), transport).login({ email: "admin@example.com", password: "uma senha longa válida" }))
      .rejects.toMatchObject({ status, code });
  });

  it("rejects invalid responses and times out", async () => {
    await expect(createInternalAuthClient(testEnv(), async () => Response.json({ ...response(), csrf_token: "secret" }, { status: 201 })).login({
      email: "admin@example.com", password: "uma senha longa válida",
    })).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    const env = testEnv({ API_TIMEOUT_MS: "100" });
    const hanging: typeof fetch = (_url, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("secret"))));
    await expect(createInternalAuthClient(env, hanging).login({ email: "admin@example.com", password: "uma senha longa válida" }))
      .rejects.toMatchObject({ code: "TIMEOUT", status: 504 });
  });
});

describe("internal BFF routes", () => {
  it("creates only an encrypted HttpOnly cookie and redirects with 303", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(response(), { status: 201 })));
    const loginCookie = cookieSettings(testEnv(), "login", 0);
    const csrf = "E".repeat(43);
    const request = post("/auth/login", new URLSearchParams({ csrf, email: "admin@example.com", password: "uma senha longa válida" }).toString(), `${loginCookie.name}=${csrf}`);
    const result = await startLogin(request);
    expect(result.status).toBe(303);
    expect(result.headers.get("location")).toBe("http://127.0.0.1:3000/dashboard");
    const authCookie = result.cookies.get(cookieSettings(testEnv(), "internal-session", 0).name);
    expect(authCookie).toMatchObject({ httpOnly: true, sameSite: "lax", secure: false, path: "/" });
    expect(authCookie?.value).not.toContain(sessionToken);
    expect(authCookie?.value).not.toContain(apiCsrf);
    expect(JSON.stringify(await result.text())).not.toContain(sessionToken);
  });

  it.each([
    ["csrf=wrong&email=admin%40example.com&password=uma+senha+longa+v%C3%A1lida", "wrong CSRF"],
    [`csrf=${"E".repeat(43)}&csrf=${"E".repeat(43)}&email=admin%40example.com&password=uma+senha+longa+v%C3%A1lida`, "repeated CSRF"],
    [`csrf=${"E".repeat(43)}&email=admin%40example.com&password=uma+senha+longa+v%C3%A1lida&role=admin`, "unexpected field"],
  ])("rejects %s before calling FastAPI", async (body) => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    const name = cookieSettings(testEnv(), "login", 0).name;
    const result = await startLogin(post("/auth/login", body, `${name}=${"E".repeat(43)}`));
    expect(result.status).toBe(403); expect(fetchMock).not.toHaveBeenCalled();
  });

  it("revokes with the API CSRF, clears on 204 and rejects replay", async () => {
    const expires = Date.now() + 60_000;
    const sealed = sealInternalSession({ version: 1, mode: "internal", sessionToken, apiCsrf, browserCsrf, absoluteExpiresAt: expires }, key);
    const name = cookieSettings(testEnv(), "internal-session", 0).name;
    const transport = vi.fn(async (_url: URL | RequestInfo, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("authorization")).toBe(`Bearer ${sessionToken}`);
      expect(new Headers(init?.headers).get("x-csrf-token")).toBe(apiCsrf);
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal("fetch", transport);
    const result = await logout(post("/auth/logout", `csrf=${browserCsrf}`, `${name}=${sealed}`));
    expect(result.status).toBe(303); expect(result.cookies.get(name)?.value).toBe("");
    const replay = await logout(post("/auth/logout", `csrf=${browserCsrf}`, `${name}=`));
    expect(replay.status).toBe(401); expect(transport).toHaveBeenCalledTimes(1);
  });

  it("retains the local session when remote revocation is unavailable", async () => {
    const sealed = sealInternalSession({ version: 1, mode: "internal", sessionToken, apiCsrf, browserCsrf, absoluteExpiresAt: Date.now() + 60_000 }, key);
    const name = cookieSettings(testEnv(), "internal-session", 0).name;
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
    const result = await logout(post("/auth/logout", `csrf=${browserCsrf}`, `${name}=${sealed}`));
    expect(result.status).toBe(503); expect(result.headers.get("set-cookie")).toBeNull();
    expect(await result.json()).toEqual({ error: "Autenticação indisponível." });
  });
});
