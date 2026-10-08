import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cookieSettings, getAuthRuntime } from "./session";
import { createApiClient } from "../api/client";
import { ApiError } from "../api/errors";

export async function requireSession() {
  let auth;
  try { auth = getAuthRuntime(); } catch { redirect("/login"); }
  const jar = await cookies();
  const id = jar.get(cookieSettings(auth.env, "session", 0).name)?.value;
  if (!id) redirect("/login");
  const session = await auth.store.readSession(id);
  if (!session) redirect("/login");
  return { auth, id, session };
}
/** Call at every protected data/page entry, not only in the persistent layout. */
export async function requireDashboard() {
  const { auth, id } = await requireSession();
  const api = createApiClient(auth.env, auth.store, id);
  try { await api.ready(); return undefined; }
  catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    if (error instanceof ApiError) return { message: error.message, requestId: error.requestId };
    return { message: "Serviço temporariamente indisponível." };
  }
}
