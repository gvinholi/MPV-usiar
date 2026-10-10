import "server-only";
import { z } from "zod";

const optionalText = z.preprocess(v => v === "" ? undefined : v, z.string().trim().min(1).optional());
const configSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  AUTH_MODE: z.enum(["internal", "oidc"]),
  AUTH_COOKIE_KEY: optionalText,
  APP_ORIGIN: z.string().default("http://127.0.0.1:3000"),
  FASTAPI_BASE_URL: z.string().default("http://127.0.0.1:8000"),
  API_TIMEOUT_MS: z.coerce.number().int().min(100).max(30000).default(10000),
  SESSION_IDLE_SECONDS: z.coerce.number().int().min(60).max(28800).default(1800),
  SESSION_ABSOLUTE_SECONDS: z.coerce.number().int().min(60).max(86400).default(28800),
  API_PROFILE_ID: optionalText,
  API_PROFILE_CODE: optionalText,
  OIDC_ISSUER: optionalText,
  OIDC_CLIENT_ID: optionalText,
  OIDC_CLIENT_AUTH_METHOD: optionalText,
  OIDC_CLIENT_SECRET: optionalText,
  OIDC_SCOPES: z.string().default("openid dashboard:read"),
  OIDC_RESOURCE: optionalText,
  OIDC_AUDIENCE: optionalText,
  OIDC_ID_TOKEN_ALG: z.enum(["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"]).default("RS256"),
});

export class ConfigurationError extends Error {
  constructor() { super("Configuração do servidor indisponível ou inválida."); }
}

function decodeCookieKey(value: string | undefined) {
  if (!value || !/^[A-Za-z0-9_-]{43}$/.test(value)) throw new ConfigurationError();
  const decoded = Buffer.from(value, "base64url");
  if (decoded.length !== 32 || decoded.toString("base64url") !== value) throw new ConfigurationError();
  return decoded;
}

function checkedUrl(value: string, production: boolean, oidc = false): URL {
  const url = new URL(value);
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (value !== value.trim() || /\s/.test(value) || url.username || url.password || url.hash || url.search ||
    (url.protocol !== "https:" && !(url.protocol === "http:" && loopback && !production && !oidc))) {
    throw new ConfigurationError();
  }
  return url;
}

export function readEnvironment(raw: Record<string, string | undefined> = process.env) {
  try {
    // This application has no public environment contract. Reject accidental secrets there.
    if (Object.keys(raw).some(key => key.startsWith("NEXT_PUBLIC_") && raw[key])) throw new ConfigurationError();
    const value = configSchema.parse(raw);
    const production = value.NODE_ENV === "production";
    const origin = checkedUrl(value.APP_ORIGIN, production);
    const api = checkedUrl(value.FASTAPI_BASE_URL, production);
    if (origin.pathname !== "/" || api.pathname !== "/") throw new ConfigurationError();
    if (production && (!raw.APP_ORIGIN || !raw.FASTAPI_BASE_URL)) throw new ConfigurationError();
    if (value.SESSION_IDLE_SECONDS > value.SESSION_ABSOLUTE_SECONDS) throw new ConfigurationError();
    // Profile selection is validated at each profile-scoped page before any API call.
    // Keeping it separate lets authentication stay available to report a safe configuration state.
    let authCookieKey: Buffer | undefined;
    if (value.AUTH_MODE === "internal") {
      authCookieKey = decodeCookieKey(value.AUTH_COOKIE_KEY);
    } else {
      if (!value.OIDC_ISSUER || !value.OIDC_CLIENT_ID || !value.OIDC_CLIENT_AUTH_METHOD) throw new ConfigurationError();
      checkedUrl(value.OIDC_ISSUER, production, true);
      if (!["client_secret_basic", "client_secret_post", "none"].includes(value.OIDC_CLIENT_AUTH_METHOD)) throw new ConfigurationError();
      if ((value.OIDC_CLIENT_AUTH_METHOD === "none") === Boolean(value.OIDC_CLIENT_SECRET)) throw new ConfigurationError();
      const scopes = value.OIDC_SCOPES.split(/\s+/).filter(Boolean);
      if (!scopes.includes("openid") || scopes.includes("offline_access") || scopes.some(s => !/^[\x21\x23-\x5B\x5D-\x7E]+$/.test(s))) throw new ConfigurationError();
      if (value.OIDC_RESOURCE) checkedUrl(value.OIDC_RESOURCE, production, true);
    }
    return { ...value, APP_ORIGIN: origin.origin, FASTAPI_BASE_URL: api.origin, configured: true, production, authCookieKey };
  } catch { throw new ConfigurationError(); }
}
export type Environment = ReturnType<typeof readEnvironment>;
