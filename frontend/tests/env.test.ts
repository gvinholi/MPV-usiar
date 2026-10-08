import { describe, expect, it } from "vitest";
import { readEnvironment, ConfigurationError } from "../src/lib/server/env";
import { MemorySessionStore } from "../src/lib/server/auth/session-store";
import { getAuthRuntime } from "../src/lib/server/auth/session";
import { vi } from "vitest";
import { testEnv, oidcEnv } from "./helpers";

describe("server configuration", () => {
  it("starts locally without a provider, with authentication unavailable", () => {
    expect(testEnv().configured).toBe(false); expect(oidcEnv().configured).toBe(true);
  });
  it.each([
    { OIDC_ISSUER: "https://issuer.test" }, { OIDC_CLIENT_SECRET: "do-not-leak" },
    { FASTAPI_BASE_URL: "https://user:secret@api.test" }, { FASTAPI_BASE_URL: "https://api.test/path" },
    { FASTAPI_BASE_URL: "http://api.test" }, { APP_ORIGIN: "https://app.test?redirect=evil" },
    { OIDC_SCOPES: "openid offline_access" }, { OIDC_SCOPES: "dashboard:read" },
    { API_TIMEOUT_MS: "0" }, { SESSION_IDLE_SECONDS: "200", SESSION_ABSOLUTE_SECONDS: "100" },
    { API_PROFILE_ID: "invalid" }, { API_PROFILE_ID: "a", API_PROFILE_CODE: "USIAR" },
    { NEXT_PUBLIC_CLIENT_SECRET: "do-not-leak" },
  ])("rejects invalid configuration without echoing values: %j", raw => {
    expect(() => testEnv(raw)).toThrow(ConfigurationError);
    try { testEnv(raw); } catch (error) { expect(String(error)).not.toContain("do-not-leak"); }
  });
  it("requires HTTPS OIDC even in development", () => {
    expect(() => testEnv({ OIDC_ISSUER: "http://localhost:9000", OIDC_CLIENT_ID: "test", OIDC_CLIENT_AUTH_METHOD: "none" })).toThrow();
  });
  it("does not silently use memory in production", () => {
    expect(() => new MemorySessionStore(1000, Date.now, "production")).toThrow();
    expect(() => readEnvironment({ NODE_ENV: "production" })).toThrow();
    vi.stubEnv("NODE_ENV", "production"); vi.stubEnv("APP_ORIGIN", "https://app.test"); vi.stubEnv("FASTAPI_BASE_URL", "https://api.test");
    expect(() => getAuthRuntime()).toThrow("Armazenamento compartilhado");
  });
});
