import "server-only";
import { z } from "zod";

const optionalText = z.preprocess(v => v === "" ? undefined : v, z.string().trim().min(1).optional());
const configSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
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
    if (value.API_PROFILE_ID && value.API_PROFILE_CODE) throw new ConfigurationError();
    if (value.API_PROFILE_ID) z.uuid().parse(value.API_PROFILE_ID);
    const configured = Boolean(value.OIDC_ISSUER || value.OIDC_CLIENT_ID || value.OIDC_CLIENT_AUTH_METHOD || value.OIDC_CLIENT_SECRET);
    if (configured) {
      if (!value.OIDC_ISSUER || !value.OIDC_CLIENT_ID || !value.OIDC_CLIENT_AUTH_METHOD) throw new ConfigurationError();
      checkedUrl(value.OIDC_ISSUER, production, true);
      if (!["client_secret_basic", "client_secret_post", "none"].includes(value.OIDC_CLIENT_AUTH_METHOD)) throw new ConfigurationError();
      if ((value.OIDC_CLIENT_AUTH_METHOD === "none") === Boolean(value.OIDC_CLIENT_SECRET)) throw new ConfigurationError();
    } else if (value.OIDC_RESOURCE || value.OIDC_AUDIENCE) throw new ConfigurationError();
    const scopes = value.OIDC_SCOPES.split(/\s+/).filter(Boolean);
    if (!scopes.includes("openid") || scopes.includes("offline_access") || scopes.some(s => !/^[\x21\x23-\x5B\x5D-\x7E]+$/.test(s))) throw new ConfigurationError();
    if (value.OIDC_RESOURCE) checkedUrl(value.OIDC_RESOURCE, production, true);
    return { ...value, APP_ORIGIN: origin.origin, FASTAPI_BASE_URL: api.origin, configured, production };
  } catch { throw new ConfigurationError(); }
}
export type Environment = ReturnType<typeof readEnvironment>;
