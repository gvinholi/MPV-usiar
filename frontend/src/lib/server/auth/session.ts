import "server-only";
import type { Environment } from "../env";
import { readEnvironment } from "../env";
import { MemorySessionStore, randomSecret, type SessionStore } from "./session-store";
import { AuthenticationError, createOidcClient } from "./oidc";
import { sameSecret } from "./csrf";

export const TRANSACTION_SECONDS = 300;
export type CookieKind = "session" | "internal-session" | "login";
export function cookieSettings(env: Environment, kind: CookieKind, maxAge: number) {
  return { name: `${env.production ? "__Host-" : ""}usiar-${kind}`, httpOnly: true,
    secure: env.production || env.APP_ORIGIN.startsWith("https:"), sameSite: "lax" as const, path: "/", maxAge };
}
export function createAuthService(env: Environment, store: SessionStore, provider = createOidcClient(env), clock = Date.now) {
  return {
    env, store,
    async prepareLogin() {
      const csrf = randomSecret();
      const id = await store.createTransaction({ csrf, expiresAt: clock() + TRANSACTION_SECONDS * 1000 });
      return { id, csrf };
    },
    async startLogin(id: string) {
      const previous = await store.consumeTransaction(id);
      if (!previous || previous.state) throw new AuthenticationError();
      const tx = { csrf: randomSecret(), state: randomSecret(), nonce: randomSecret(), verifier: randomSecret(),
        expiresAt: clock() + TRANSACTION_SECONDS * 1000 };
      const url = await provider.authorize(tx);
      const transactionId = await store.createTransaction(tx);
      return { url, transactionId };
    },
    async completeLogin(id: string, url: URL, previousSessionId?: string) {
      // Consume before any await on the provider: one callback can win, even on failure.
      const tx = await store.consumeTransaction(id);
      if (!tx?.state || !tx.nonce || !tx.verifier || url.origin !== env.APP_ORIGIN || url.pathname !== "/auth/callback" ||
        url.searchParams.getAll("state").length !== 1 || !sameSecret(tx.state, url.searchParams.get("state") ?? "")) throw new AuthenticationError();
      const tokens = await provider.exchange(url, tx);
      if (previousSessionId) await store.deleteSession(previousSessionId);
      const now = clock();
      const seconds = Math.min(env.SESSION_ABSOLUTE_SECONDS, tokens.expiresIn);
      const sessionId = await store.createSession({ accessToken: tokens.accessToken, subject: tokens.subject,
        csrf: randomSecret(), createdAt: now, lastSeenAt: now, expiresAt: now + seconds * 1000 });
      return { sessionId, maxAge: Math.floor(seconds) };
    },
  };
}
type Runtime = ReturnType<typeof createAuthService>;
const globalRuntime = globalThis as typeof globalThis & { usiarAuth?: Runtime };
export function getAuthRuntime(): Runtime {
  const env = readEnvironment();
  if (env.AUTH_MODE !== "oidc") throw new Error("OIDC authentication is not active.");
  // Never select an in-memory fallback in production. Build is allowed; requests fail closed.
  if (env.production) throw new Error("Armazenamento compartilhado de sessões ainda não configurado.");
  if (!globalRuntime.usiarAuth) globalRuntime.usiarAuth = createAuthService(env,
    new MemorySessionStore(env.SESSION_IDLE_SECONDS * 1000, Date.now, env.NODE_ENV));
  return globalRuntime.usiarAuth;
}
