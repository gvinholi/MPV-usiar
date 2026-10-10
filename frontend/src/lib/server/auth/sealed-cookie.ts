import "server-only";
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { z } from "zod";

const AAD = Buffer.from("mpv-usiar:internal-session:v1", "utf8");
const MAX_COOKIE_LENGTH = 2048;
const secret = z.string().regex(/^[A-Za-z0-9_-]{43}$/);
const sessionToken = z.string().regex(
  /^usiar_s1\.[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/,
);
const payloadSchema = z.object({
  version: z.literal(1),
  mode: z.literal("internal"),
  sessionToken,
  apiCsrf: secret,
  browserCsrf: secret,
  absoluteExpiresAt: z.number().int().positive(),
}).strict();

export type InternalCookiePayload = z.infer<typeof payloadSchema>;

function decodePart(value: string, expectedLength?: number) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("Invalid sealed session.");
  const decoded = Buffer.from(value, "base64url");
  if (decoded.toString("base64url") !== value || (expectedLength && decoded.length !== expectedLength)) {
    throw new Error("Invalid sealed session.");
  }
  return decoded;
}

export function sealInternalSession(
  payload: InternalCookiePayload,
  key: Buffer,
  iv: Buffer = randomBytes(12),
) {
  const parsed = payloadSchema.parse(payload);
  if (key.length !== 32 || iv.length !== 12) throw new Error("Invalid sealed session configuration.");
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(AAD);
  const encrypted = Buffer.concat([
    cipher.update(JSON.stringify(parsed), "utf8"),
    cipher.final(),
  ]);
  const result = `v1.${iv.toString("base64url")}.${encrypted.toString("base64url")}.${cipher.getAuthTag().toString("base64url")}`;
  if (result.length > MAX_COOKIE_LENGTH) throw new Error("Invalid sealed session.");
  return result;
}

export function openInternalSession(value: string, key: Buffer, clock = Date.now) {
  if (typeof value !== "string" || value.length > MAX_COOKIE_LENGTH || key.length !== 32) {
    throw new Error("Invalid sealed session.");
  }
  const parts = value.split(".");
  if (parts.length !== 4 || parts[0] !== "v1") throw new Error("Invalid sealed session.");
  try {
    const iv = decodePart(parts[1]!, 12);
    const encrypted = decodePart(parts[2]!);
    const tag = decodePart(parts[3]!, 16);
    const decipher = createDecipheriv("aes-256-gcm", key, iv);
    decipher.setAAD(AAD);
    decipher.setAuthTag(tag);
    const plaintext = Buffer.concat([decipher.update(encrypted), decipher.final()]);
    if (plaintext.length > 1024) throw new Error("Invalid sealed session.");
    const parsed = payloadSchema.parse(JSON.parse(plaintext.toString("utf8")));
    if (parsed.absoluteExpiresAt <= clock()) throw new Error("Expired sealed session.");
    return parsed;
  } catch {
    throw new Error("Invalid sealed session.");
  }
}
