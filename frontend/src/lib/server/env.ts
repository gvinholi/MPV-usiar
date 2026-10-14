import "server-only";
import { z } from "zod";

const optionalText = z.preprocess((value) => value === "" ? undefined : value, z.string().trim().min(1).optional());
const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  APP_ORIGIN: z.string().default("http://127.0.0.1:3000"),
  AUTH_MODE: z.enum(["supabase", "internal", "oidc"]).default("supabase"),
  AUTH_COOKIE_KEY: optionalText,
  DATABASE_URL: z.string().min(1).default("postgresql://usiar:usiar@127.0.0.1:5432/usiar"),
  SUPABASE_URL: z.url().default("http://127.0.0.1:54321"),
  SUPABASE_ANON_KEY: z.string().min(20).default("test-only-anon-key-000000000"),
  FASTAPI_BASE_URL: z.string().default("http://127.0.0.1:8000"),
  API_TIMEOUT_MS: z.coerce.number().int().min(100).max(30000).default(10000),
  SESSION_IDLE_SECONDS: z.coerce.number().int().min(60).max(28800).default(1800),
  SESSION_ABSOLUTE_SECONDS: z.coerce.number().int().min(60).max(86400).default(28800),
  API_PROFILE_ID: optionalText,
  API_PROFILE_CODE: optionalText,
  OIDC_ISSUER: optionalText, OIDC_CLIENT_ID: optionalText, OIDC_CLIENT_AUTH_METHOD: optionalText,
  OIDC_CLIENT_SECRET: optionalText, OIDC_SCOPES: z.string().default("openid dashboard:read"),
  OIDC_RESOURCE: optionalText, OIDC_AUDIENCE: optionalText,
  OIDC_ID_TOKEN_ALG: z.enum(["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"]).default("RS256"),
});

export class ConfigurationError extends Error {
  constructor() { super("Configuração do servidor indisponível ou inválida."); }
}

function secureOrigin(value: string, production: boolean) {
  const url = new URL(value);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
      (url.protocol !== "https:" && !(url.protocol === "http:" && local && !production))) throw new ConfigurationError();
  return url.origin;
}

export function readEnvironment(raw: Record<string, string | undefined> = process.env) {
  try {
    if (Object.keys(raw).some((key) => key.startsWith("NEXT_PUBLIC_") && raw[key])) throw new ConfigurationError();
    if (Object.prototype.hasOwnProperty.call(raw, "AUTH_MODE") && raw.AUTH_MODE === undefined) throw new ConfigurationError();
    const value = schema.parse(raw);
    const production = value.NODE_ENV === "production";
    const database = new URL(value.DATABASE_URL);
    if (!["postgres:", "postgresql:"].includes(database.protocol) || !database.hostname) throw new ConfigurationError();
    const supabase = new URL(value.SUPABASE_URL);
    if (supabase.protocol !== "https:" && production && value.AUTH_MODE === "supabase") throw new ConfigurationError();
    const api = secureOrigin(value.FASTAPI_BASE_URL, production);
    if (value.SESSION_IDLE_SECONDS > value.SESSION_ABSOLUTE_SECONDS) throw new ConfigurationError();
    let authCookieKey: Buffer | undefined;
    if (value.AUTH_MODE === "internal") {
      if (!value.AUTH_COOKIE_KEY || !/^[A-Za-z0-9_-]{43}$/.test(value.AUTH_COOKIE_KEY)) throw new ConfigurationError();
      const decoded = Buffer.from(value.AUTH_COOKIE_KEY, "base64url");
      if (decoded.length !== 32) throw new ConfigurationError();
      authCookieKey = decoded;
    }
    if (value.AUTH_MODE === "oidc") {
      if (!value.OIDC_ISSUER || !value.OIDC_CLIENT_ID || !value.OIDC_CLIENT_AUTH_METHOD) throw new ConfigurationError();
      if (new URL(value.OIDC_ISSUER).protocol !== "https:") throw new ConfigurationError();
      const scopes = value.OIDC_SCOPES.split(/\s+/); if (!scopes.includes("openid") || scopes.includes("offline_access")) throw new ConfigurationError();
    }
    if (production && value.AUTH_MODE === "supabase" && (!raw.APP_ORIGIN || !raw.DATABASE_URL || !raw.SUPABASE_URL || !raw.SUPABASE_ANON_KEY)) throw new ConfigurationError();
    return { ...value, APP_ORIGIN: secureOrigin(value.APP_ORIGIN, production), FASTAPI_BASE_URL: api, production, configured: true, authCookieKey };
  } catch { throw new ConfigurationError(); }
}

export type Environment = ReturnType<typeof readEnvironment>;
