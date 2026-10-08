import { beforeEach, describe, expect, it, vi } from "vitest";
import { exportJWK, generateKeyPair, SignJWT } from "jose";
import { createOidcClient } from "../src/lib/server/auth/oidc";
import { createAuthService } from "../src/lib/server/auth/session";
import { MemorySessionStore } from "../src/lib/server/auth/session-store";
import { oidcEnv } from "./helpers";
import { createHash } from "node:crypto";

const keys = await generateKeyPair("RS256");
const wrongKeys = await generateKeyPair("RS256");
const jwk = { ...await exportJWK(keys.publicKey), kid: "test-key", alg: "RS256", use: "sig" };
const env = oidcEnv();
let nonce = ""; let challenge = ""; let invalid: string | undefined;
let exchangeCount = 0;
let calls: { url: string; init?: RequestInit }[];

beforeEach(() => {
  invalid = undefined; calls = []; exchangeCount = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push({ url, init });
    if (url.endsWith("/.well-known/openid-configuration")) return Response.json({
      issuer: invalid === "discovery-issuer" ? "https://wrong.test" : env.OIDC_ISSUER,
      authorization_endpoint: "https://issuer.test/authorize", token_endpoint: "https://issuer.test/token",
      jwks_uri: "https://issuer.test/jwks", response_types_supported: ["code"], subject_types_supported: ["public"],
      id_token_signing_alg_values_supported: ["RS256"], code_challenge_methods_supported: ["S256"],
    });
    if (url.endsWith("/jwks")) return Response.json({ keys: [jwk] });
    if (url.endsWith("/token")) {
      exchangeCount++;
      const body = new URLSearchParams(String(init?.body));
      const actual = createHash("sha256").update(body.get("code_verifier") ?? "").digest("base64url");
      if (invalid === "pkce" || actual !== challenge) return Response.json({ error: "invalid_grant" }, { status: 400 });
      if (invalid === "network") throw new Error("internal-secret");
      const token = await new SignJWT({ nonce: invalid === "nonce" ? "wrong" : nonce })
        .setProtectedHeader({ alg: "RS256", kid: "test-key" }).setSubject("test-user")
        .setIssuer(invalid === "issuer" ? "https://wrong.test" : env.OIDC_ISSUER!)
        .setAudience(invalid === "audience" ? "wrong" : env.OIDC_CLIENT_ID!)
        .setIssuedAt().setExpirationTime(invalid === "expired" ? "-1h" : "5m")
        .sign(invalid === "signature" ? wrongKeys.privateKey : keys.privateKey);
      return Response.json({ access_token: "test-only-access-secret", id_token: token, refresh_token: "must-not-store", token_type: "Bearer", expires_in: 120 });
    }
    throw new Error("Unexpected test endpoint");
  }));
});
async function started() {
  const store = new MemorySessionStore(1800000, Date.now, "test");
  const auth = createAuthService(env, store, createOidcClient(env));
  const pre = await auth.prepareLogin(); const login = await auth.startLogin(pre.id);
  nonce = login.url.searchParams.get("nonce")!; challenge = login.url.searchParams.get("code_challenge")!;
  const url = new URL("/auth/callback", env.APP_ORIGIN);
  url.searchParams.set("code", "test-code"); url.searchParams.set("state", login.url.searchParams.get("state")!);
  return { store, auth, login, url };
}
describe("OIDC code flow with actual signed ID tokens", () => {
  it("uses discovery, S256, state, nonce and verifies the signature before storing tokens", async () => {
    const { auth, store, login, url } = await started();
    expect(login.url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(login.url.searchParams.get("response_type")).toBe("code");
    expect(login.url.href).not.toContain(env.OIDC_CLIENT_SECRET);
    const result = await auth.completeLogin(login.transactionId, url);
    const session = await store.readSession(result.sessionId);
    expect(session?.accessToken).toBe("test-only-access-secret"); expect(result.maxAge).toBe(120);
    expect(session).not.toHaveProperty("refreshToken"); expect(session).not.toHaveProperty("idToken");
    expect(calls.some(c => c.url.endsWith("/jwks"))).toBe(true);
    expect(calls.every(c => c.init?.redirect === "error")).toBe(true);
    expect(JSON.stringify(result)).not.toContain("access-secret");
    await expect(auth.completeLogin(login.transactionId, url)).rejects.toThrow(); expect(exchangeCount).toBe(1);
  });
  it.each(["nonce", "pkce", "signature", "issuer", "audience", "expired", "network"])("rejects %s failures and consumes transaction", async failure => {
    const { auth, login, url } = await started(); invalid = failure;
    await expect(auth.completeLogin(login.transactionId, url)).rejects.toThrow("Não foi possível concluir");
    await expect(auth.completeLogin(login.transactionId, url)).rejects.toThrow(); expect(exchangeCount).toBe(1);
  });
  it("rejects mismatched discovery issuer", async () => {
    invalid = "discovery-issuer"; await expect(started()).rejects.toThrow();
  });
  it("rejects wrong state before exchanging code", async () => {
    const { auth, login, url } = await started(); url.searchParams.set("state", "wrong");
    await expect(auth.completeLogin(login.transactionId, url)).rejects.toThrow(); expect(exchangeCount).toBe(0);
  });
  it("rejects callback origin substitution and missing transaction", async () => {
    const { auth, login, url } = await started(); url.host = "evil.test";
    await expect(auth.completeLogin(login.transactionId, url)).rejects.toThrow();
    await expect(auth.completeLogin("missing", url)).rejects.toThrow(); expect(exchangeCount).toBe(0);
  });
  it("rotates session identity after reauthentication", async () => {
    const { auth, store, login, url } = await started();
    const old = await store.createSession({ accessToken: "old", subject: "old", csrf: "old", createdAt: Date.now(), lastSeenAt: Date.now(), expiresAt: Date.now() + 10000 });
    const result = await auth.completeLogin(login.transactionId, url, old);
    expect(result.sessionId).not.toBe(old); expect(await store.readSession(old)).toBeUndefined();
  });
});
