import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { readEnvironment, type Environment } from "../env";
import { cookieSettings, getAuthRuntime, TRANSACTION_SECONDS } from "./session";
import { CsrfError, verifyCsrf, verifyForm } from "./csrf";
import { AuthenticationError } from "./oidc";
import { randomSecret } from "./session-store";
import { createInternalAuthClient, InternalAuthApiError } from "./internal";
import { openInternalSession, sealInternalSession } from "./sealed-cookie";

export function authFailure(error: unknown) {
  const status = error instanceof CsrfError ? 403 : error instanceof AuthenticationError ? 401 : 503;
  return NextResponse.json({ error: status === 503 ? "Autenticação indisponível." : "Não foi possível autorizar a solicitação." },
    { status, headers: { "Cache-Control": "private, no-store" } });
}

function redirectTo(env: Environment, path: string) {
  const response = NextResponse.redirect(new URL(path, env.APP_ORIGIN), 303);
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

function clearCookie(response: NextResponse, env: Environment, kind: "session" | "internal-session" | "login") {
  response.cookies.set({ ...cookieSettings(env, kind, 0), value: "", expires: new Date(0) });
}

function refreshInternalLogin(response: NextResponse, env: Environment) {
  response.cookies.set({
    ...cookieSettings(env, "login", TRANSACTION_SECONDS),
    value: randomSecret(),
  });
}

export async function prepareLogin(request?: NextRequest) {
  try {
    const env = readEnvironment();
    if (env.AUTH_MODE === "internal") {
      const requestedError = request ? new URL(request.url).searchParams.get("error") : null;
      const response = redirectTo(env, requestedError === "session" ? "/login?error=session" : "/login");
      refreshInternalLogin(response, env);
      clearCookie(response, env, "session");
      return response;
    }
    const auth = getAuthRuntime();
    const tx = await auth.prepareLogin();
    const response = redirectTo(env, "/login");
    response.cookies.set({ ...cookieSettings(env, "login", TRANSACTION_SECONDS), value: tx.id });
    clearCookie(response, env, "internal-session");
    return response;
  } catch (error) { return authFailure(error); }
}

async function internalLogin(request: NextRequest, env: Environment) {
  const loginCookie = cookieSettings(env, "login", 0);
  const expected = request.cookies.get(loginCookie.name)?.value ?? "";
  const form = await verifyForm(request, env.APP_ORIGIN, expected, ["csrf", "email", "password"], 8192);
  try {
    const created = await createInternalAuthClient(env).login({
      email: form.get("email") ?? "",
      password: form.get("password") ?? "",
    });
    const absoluteExpiresAt = Date.parse(created.absolute_expires_at);
    const maxAge = Math.floor((absoluteExpiresAt - Date.now()) / 1000);
    if (maxAge < 1 || !env.authCookieKey) throw new InternalAuthApiError(502, "INVALID_RESPONSE");
    const sealed = sealInternalSession({
      version: 1,
      mode: "internal",
      sessionToken: created.session_token,
      apiCsrf: created.csrf_token,
      browserCsrf: randomSecret(),
      absoluteExpiresAt,
    }, env.authCookieKey);
    const response = redirectTo(env, "/dashboard");
    response.cookies.set({ ...cookieSettings(env, "internal-session", maxAge), value: sealed });
    clearCookie(response, env, "login");
    clearCookie(response, env, "session");
    return response;
  } catch (error) {
    if (!(error instanceof InternalAuthApiError)) throw error;
    const kind = error.code === "RATE_LIMITED" ? "rate-limited" :
      ["UNAVAILABLE", "TIMEOUT", "INVALID_RESPONSE"].includes(error.code) ? "unavailable" : "authentication";
    const response = redirectTo(env, `/login?error=${kind}`);
    refreshInternalLogin(response, env);
    return response;
  }
}

export async function startLogin(request: NextRequest) {
  try {
    const env = readEnvironment();
    if (env.AUTH_MODE === "internal") return await internalLogin(request, env);
    const auth = getAuthRuntime();
    const id = request.cookies.get(cookieSettings(env, "login", 0).name)?.value ?? "";
    const tx = await auth.store.readTransaction(id);
    if (!tx || tx.state) throw new CsrfError();
    await verifyCsrf(request, env.APP_ORIGIN, tx.csrf);
    const login = await auth.startLogin(id);
    const response = NextResponse.redirect(login.url, 303);
    response.cookies.set({ ...cookieSettings(env, "login", TRANSACTION_SECONDS), value: login.transactionId });
    return response;
  } catch (error) { return authFailure(error); }
}

export async function callback(request: NextRequest) {
  try {
    const env = readEnvironment();
    if (env.AUTH_MODE !== "oidc") return NextResponse.json(
      { error: "Não foi possível autorizar a solicitação." },
      { status: 403, headers: { "Cache-Control": "private, no-store" } },
    );
    const auth = getAuthRuntime();
    const loginCookie = cookieSettings(env, "login", 0);
    const sessionCookie = cookieSettings(env, "session", 0);
    const id = request.cookies.get(loginCookie.name)?.value ?? "";
    const url = new URL("/auth/callback", env.APP_ORIGIN);
    url.search = new URL(request.url).search;
    try {
      const session = await auth.completeLogin(id, url, request.cookies.get(sessionCookie.name)?.value);
      const response = redirectTo(env, "/dashboard");
      response.cookies.set({ ...cookieSettings(env, "session", session.maxAge), value: session.sessionId });
      clearCookie(response, env, "login");
      clearCookie(response, env, "internal-session");
      return response;
    } catch {
      const response = redirectTo(env, "/login?error=authentication");
      clearCookie(response, env, "login");
      return response;
    }
  } catch (error) { return authFailure(error); }
}

async function internalLogout(request: NextRequest, env: Environment) {
  const cookie = cookieSettings(env, "internal-session", 0);
  const sealed = request.cookies.get(cookie.name)?.value ?? "";
  if (!env.authCookieKey) throw new AuthenticationError();
  let session;
  try { session = openInternalSession(sealed, env.authCookieKey); }
  catch { throw new AuthenticationError(); }
  await verifyCsrf(request, env.APP_ORIGIN, session.browserCsrf);
  try {
    await createInternalAuthClient(env).logout(session.sessionToken, session.apiCsrf);
  } catch (error) {
    if (!(error instanceof InternalAuthApiError) || error.status !== 401) throw error;
  }
  const response = redirectTo(env, "/login");
  clearCookie(response, env, "internal-session");
  clearCookie(response, env, "login");
  return response;
}

export async function logout(request: NextRequest) {
  try {
    const env = readEnvironment();
    if (env.AUTH_MODE === "internal") return await internalLogout(request, env);
    const auth = getAuthRuntime();
    const cookie = cookieSettings(env, "session", 0);
    const id = request.cookies.get(cookie.name)?.value ?? "";
    const session = await auth.store.readSession(id);
    if (!session) throw new AuthenticationError();
    await verifyCsrf(request, env.APP_ORIGIN, session.csrf);
    await auth.store.deleteSession(id);
    const response = redirectTo(env, "/login");
    clearCookie(response, env, "session");
    return response;
  } catch (error) { return authFailure(error); }
}
