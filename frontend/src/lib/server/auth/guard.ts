import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { readEnvironment } from "../env";
import { cookieSettings, getAuthRuntime } from "./session";
import { openInternalSession } from "./sealed-cookie";
import { createApiClient, type BearerCredential } from "../api/client";
import { ApiError } from "../api/errors";

export async function requireSession() {
  let env;
  try { env = readEnvironment(); } catch { redirect("/login"); }
  const jar = await cookies();
  if (env.AUTH_MODE === "internal") {
    const sealed = jar.get(cookieSettings(env, "internal-session", 0).name)?.value;
    if (!sealed || !env.authCookieKey) redirect("/login");
    let session;
    try { session = openInternalSession(sealed, env.authCookieKey); }
    catch { redirect("/login?error=session"); }
    const credential: BearerCredential = {
      async read() { return session.sessionToken; },
      async invalidate() { /* Route Handlers own cookies; FastAPI owns validity. */ },
    };
    return { env, mode: "internal" as const, credential, browserCsrf: session.browserCsrf };
  }

  let auth;
  try { auth = getAuthRuntime(); } catch { redirect("/login"); }
  const id = jar.get(cookieSettings(env, "session", 0).name)?.value;
  if (!id) redirect("/login");
  const session = await auth.store.readSession(id);
  if (!session) redirect("/login");
  const credential: BearerCredential = {
    async read() { return (await auth.store.readSession(id))?.accessToken; },
    async invalidate() { await auth.store.deleteSession(id); },
  };
  return { env, mode: "oidc" as const, credential, browserCsrf: session.csrf };
}
/** Call at every protected data/page entry, not only in the persistent layout. */
export async function requireDashboard() {
  const session = await requireSession();
  const api = createApiClient(session.env, session.credential);
  try { await api.ready(); return undefined; }
  catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login?error=session");
    if (error instanceof ApiError) return { message: error.message, requestId: error.requestId };
    return { message: "Serviço temporariamente indisponível." };
  }
}
