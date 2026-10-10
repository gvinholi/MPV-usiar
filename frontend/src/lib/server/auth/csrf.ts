import "server-only";
import { timingSafeEqual } from "node:crypto";

export function sameSecret(expected: string, received: string) {
  const a = Buffer.from(expected); const b = Buffer.from(received);
  return a.length > 0 && a.length === b.length && timingSafeEqual(a, b);
}
export class CsrfError extends Error {
  constructor() { super("Solicitação não autorizada."); }
}
export async function verifyForm(
  request: Request,
  origin: string,
  expected: string,
  fields: readonly string[] = ["csrf"],
  maxBytes = 2048,
) {
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
      if (size > maxBytes) { await reader.cancel(); throw new CsrfError(); }
      parts.push(chunk.value);
    }
  } finally { reader.releaseLock(); }
  const form = new URLSearchParams(Buffer.concat(parts).toString("utf8"));
  const allowed = new Set(fields);
  if ([...form.keys()].some(name => !allowed.has(name)) ||
    fields.some(name => form.getAll(name).length !== 1) ||
    !sameSecret(expected, form.get("csrf") ?? "")) throw new CsrfError();
  return form;
}

export async function verifyCsrf(request: Request, origin: string, expected: string) {
  await verifyForm(request, origin, expected);
}
