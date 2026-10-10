import { describe, expect, it } from "vitest";
import { readEnvironment, ConfigurationError } from "../src/lib/server/env";
import { MemorySessionStore } from "../src/lib/server/auth/session-store";
import { getAuthRuntime } from "../src/lib/server/auth/session";
import { vi } from "vitest";
import { testEnv, oidcEnv } from "./helpers";

describe("server configuration", () => {
  it("selects exactly one configured authentication mode", () => {
    expect(testEnv()).toMatchObject({ configured: true, AUTH_MODE: "internal" });
    expect(oidcEnv()).toMatchObject({ configured: true, AUTH_MODE: "oidc" });
  });
  it.each([
    { AUTH_MODE: undefined }, { AUTH_COOKIE_KEY: "invalid" },
    { FASTAPI_BASE_URL: "https://user:secret@api.test" }, { FASTAPI_BASE_URL: "https://api.test/path" },
    { FASTAPI_BASE_URL: "http://api.test" }, { APP_ORIGIN: "https://app.test?redirect=evil" },
    { API_TIMEOUT_MS: "0" }, { SESSION_IDLE_SECONDS: "200", SESSION_ABSOLUTE_SECONDS: "100" },
    { NEXT_PUBLIC_CLIENT_SECRET: "do-not-leak" },
  ])("rejects invalid configuration without echoing values: %j", raw => {
    expect(() => testEnv(raw)).toThrow(ConfigurationError);
    try { testEnv(raw); } catch (error) { expect(String(error)).not.toContain("do-not-leak"); }
  });
  it("requires HTTPS OIDC even in development", () => {
    expect(() => testEnv({ AUTH_MODE: "oidc", OIDC_ISSUER: "http://localhost:9000", OIDC_CLIENT_ID: "test", OIDC_CLIENT_AUTH_METHOD: "none" })).toThrow();
  });
  it.each(["openid offline_access", "dashboard:read"])("rejects unsafe OIDC scopes", scopes => {
    expect(() => testEnv({ AUTH_MODE: "oidc", OIDC_ISSUER: "https://issuer.test", OIDC_CLIENT_ID: "test", OIDC_CLIENT_AUTH_METHOD: "none", OIDC_SCOPES: scopes })).toThrow();
  });
  it("keeps profile configuration server-side for page-level validation", () => {
    expect(testEnv({ API_PROFILE_ID: "invalid" }).API_PROFILE_ID).toBe("invalid");
    expect(testEnv({ API_PROFILE_ID: "a", API_PROFILE_CODE: "USIAR" })).toMatchObject({ API_PROFILE_ID: "a", API_PROFILE_CODE: "USIAR" });
  });
  it("does not silently use memory in production", () => {
    expect(() => new MemorySessionStore(1000, Date.now, "production")).toThrow();
    expect(() => readEnvironment({ NODE_ENV: "production", AUTH_MODE: "internal", AUTH_COOKIE_KEY: "A".repeat(43) })).toThrow();
    vi.stubEnv("NODE_ENV", "production"); vi.stubEnv("AUTH_MODE", "oidc"); vi.stubEnv("APP_ORIGIN", "https://app.test"); vi.stubEnv("FASTAPI_BASE_URL", "https://api.test");
    vi.stubEnv("OIDC_ISSUER", "https://issuer.test"); vi.stubEnv("OIDC_CLIENT_ID", "client"); vi.stubEnv("OIDC_CLIENT_AUTH_METHOD", "none");
    expect(() => getAuthRuntime()).toThrow("Armazenamento compartilhado");
  });
});
