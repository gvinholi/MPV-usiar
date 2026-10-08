import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { cookieSettings, getAuthRuntime, TRANSACTION_SECONDS } from "./session";
import { CsrfError, verifyCsrf } from "./csrf";
import { AuthenticationError } from "./oidc";

export function authFailure(error: unknown) {
  const status = error instanceof CsrfError ? 403 : error instanceof AuthenticationError ? 401 : 503;
  return NextResponse.json({ error: status === 503 ? "Autenticação indisponível." : "Não foi possível autorizar a solicitação." },
    { status, headers: { "Cache-Control": "private, no-store" } });
}
export async function prepareLogin() {
  try {
    const auth = getAuthRuntime();
    if (!auth.env.configured) return authFailure(undefined);
    const tx = await auth.prepareLogin();
    const response = NextResponse.redirect(new URL("/login", auth.env.APP_ORIGIN), 303);
    response.cookies.set({ ...cookieSettings(auth.env, "login", TRANSACTION_SECONDS), value: tx.id });
    return response;
  } catch (error) { return authFailure(error); }
}
export async function startLogin(request: NextRequest) {
  try {
    const auth = getAuthRuntime();
    if (!auth.env.configured) return authFailure(undefined);
    const id = request.cookies.get(cookieSettings(auth.env, "login", 0).name)?.value ?? "";
    const tx = await auth.store.readTransaction(id);
    if (!tx || tx.state) throw new CsrfError();
    await verifyCsrf(request, auth.env.APP_ORIGIN, tx.csrf);
    const login = await auth.startLogin(id);
    const response = NextResponse.redirect(login.url, 303);
    response.cookies.set({ ...cookieSettings(auth.env, "login", TRANSACTION_SECONDS), value: login.transactionId });
    return response;
  } catch (error) { return authFailure(error); }
}
export async function callback(request: NextRequest) {
  try {
    const auth = getAuthRuntime();
    const loginCookie = cookieSettings(auth.env, "login", 0);
    const sessionCookie = cookieSettings(auth.env, "session", 0);
    const id = request.cookies.get(loginCookie.name)?.value ?? "";
    // Origin comes only from configuration, never Host or forwarded headers.
    const url = new URL("/auth/callback", auth.env.APP_ORIGIN);
    url.search = new URL(request.url).search;
    try {
      const session = await auth.completeLogin(id, url, request.cookies.get(sessionCookie.name)?.value);
      const response = NextResponse.redirect(new URL("/dashboard", auth.env.APP_ORIGIN), 303);
      response.headers.set("Referrer-Policy", "no-referrer");
      response.cookies.set({ ...cookieSettings(auth.env, "session", session.maxAge), value: session.sessionId });
      response.cookies.set({ ...loginCookie, value: "" });
      return response;
    } catch {
      const response = NextResponse.redirect(new URL("/login?error=authentication", auth.env.APP_ORIGIN), 303);
      response.headers.set("Referrer-Policy", "no-referrer");
      response.cookies.set({ ...loginCookie, value: "" });
      return response;
    }
  } catch (error) { return authFailure(error); }
}
export async function logout(request: NextRequest) {
  try {
    const auth = getAuthRuntime();
    const cookie = cookieSettings(auth.env, "session", 0);
    const id = request.cookies.get(cookie.name)?.value ?? "";
    const session = await auth.store.readSession(id);
    if (!session) throw new AuthenticationError();
    await verifyCsrf(request, auth.env.APP_ORIGIN, session.csrf);
    await auth.store.deleteSession(id);
    const response = NextResponse.redirect(new URL("/login", auth.env.APP_ORIGIN), 303);
    response.cookies.set({ ...cookie, value: "" });
    return response;
  } catch (error) { return authFailure(error); }
}
