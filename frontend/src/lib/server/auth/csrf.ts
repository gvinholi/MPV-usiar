import "server-only";
import { timingSafeEqual } from "node:crypto";

export function sameSecret(expected: string, received: string) {
  const a = Buffer.from(expected); const b = Buffer.from(received);
  return a.length > 0 && a.length === b.length && timingSafeEqual(a, b);
}
export class CsrfError extends Error {
  constructor() { super("Solicitação não autorizada."); }
}
export async function verifyCsrf(request: Request, origin: string, expected: string) {
  const site = request.headers.get("sec-fetch-site");
  if (request.method !== "POST" || request.headers.get("origin") !== origin ||
    (site !== null && site !== "same-origin") ||
    request.headers.get("content-type")?.split(";")[0] !== "application/x-www-form-urlencoded") throw new CsrfError();
  // Bounded body; never parse arbitrary uploads or multipart requests.
  const reader = request.body?.getReader();
  if (!reader) throw new CsrfError();
  let size = 0; const parts: Uint8Array[] = [];
  try {
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.length;
      if (size > 2048) { await reader.cancel(); throw new CsrfError(); }
      parts.push(chunk.value);
    }
  } finally { reader.releaseLock(); }
  const form = new URLSearchParams(Buffer.concat(parts).toString("utf8"));
  if (form.getAll("csrf").length !== 1 || !sameSecret(expected, form.get("csrf") ?? "")) throw new CsrfError();
}
