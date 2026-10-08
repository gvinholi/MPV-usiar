import { readEnvironment } from "../src/lib/server/env";
import { MemorySessionStore } from "../src/lib/server/auth/session-store";
export const testEnv = (overrides: Record<string, string | undefined> = {}) => readEnvironment({ NODE_ENV: "test", ...overrides });
export const oidcEnv = () => testEnv({ OIDC_ISSUER: "https://issuer.test", OIDC_CLIENT_ID: "test-client", OIDC_CLIENT_AUTH_METHOD: "client_secret_basic", OIDC_CLIENT_SECRET: "test-only-secret" });
export async function apiFixture() {
  const env = testEnv(); const store = new MemorySessionStore(1800000, Date.now, "test");
  const id = await store.createSession({ accessToken: "test-only-access-token", subject: "test-subject", csrf: "csrf-test",
    createdAt: Date.now(), lastSeenAt: Date.now(), expiresAt: Date.now() + 60000 });
  return { env, store, id };
}
