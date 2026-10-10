import "server-only";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { Environment } from "../env";
import {
  InternalLoginRequestSchema,
  InternalSessionResponseSchema,
  type InternalLoginRequest,
} from "../api/contracts.generated";

const sessionResponse = InternalSessionResponseSchema.extend({
  token_type: z.literal("Bearer"),
  session_token: z.string().regex(
    /^usiar_s1\.[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/,
  ),
  csrf_token: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
}).strict().superRefine((value, context) => {
  const idle = Date.parse(value.idle_expires_at);
  const absolute = Date.parse(value.absolute_expires_at);
  if (idle > absolute) context.addIssue({ code: "custom", message: "Invalid session deadlines." });
});

export type InternalSessionResult = z.infer<typeof sessionResponse>;

export class InternalAuthApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: "INVALID_INPUT" | "INVALID_CREDENTIALS" | "RATE_LIMITED" |
      "UNAVAILABLE" | "TIMEOUT" | "INVALID_RESPONSE" | "FORBIDDEN",
    public readonly retryAfter?: number,
  ) {
    super("Internal authentication request failed.");
  }
}

async function boundedJson(response: Response) {
  const reader = response.body?.getReader();
  if (!reader) throw new InternalAuthApiError(502, "INVALID_RESPONSE");
  let size = 0;
  const parts: Uint8Array[] = [];
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > 16 * 1024) {
        await reader.cancel();
        throw new InternalAuthApiError(502, "INVALID_RESPONSE");
      }
      parts.push(chunk.value);
    }
  } finally {
    reader.releaseLock();
  }
  try {
    return JSON.parse(Buffer.concat(parts).toString("utf8")) as unknown;
  } catch {
    throw new InternalAuthApiError(502, "INVALID_RESPONSE");
  }
}

function mappedError(response: Response) {
  if (response.status === 401) return new InternalAuthApiError(401, "INVALID_CREDENTIALS");
  if (response.status === 403) return new InternalAuthApiError(403, "FORBIDDEN");
  if ([413, 422].includes(response.status)) return new InternalAuthApiError(response.status, "INVALID_INPUT");
  if (response.status === 429) {
    const raw = response.headers.get("retry-after") ?? "";
    const retryAfter = /^\d{1,6}$/.test(raw) ? Math.max(1, Math.min(86400, Number(raw))) : undefined;
    return new InternalAuthApiError(429, "RATE_LIMITED", retryAfter);
  }
  if ([500, 503].includes(response.status)) return new InternalAuthApiError(response.status, "UNAVAILABLE");
  return new InternalAuthApiError(502, "INVALID_RESPONSE");
}

export function createInternalAuthClient(
  env: Environment,
  transport: typeof fetch = fetch,
  clock = Date.now,
) {
  if (env.AUTH_MODE !== "internal") throw new InternalAuthApiError(503, "UNAVAILABLE");
  const endpoint = new URL("/api/v1/auth/session", env.FASTAPI_BASE_URL);
  if (endpoint.origin !== env.FASTAPI_BASE_URL) throw new InternalAuthApiError(503, "UNAVAILABLE");

  async function execute(init: RequestInit) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), env.API_TIMEOUT_MS);
    try {
      return await transport(endpoint, {
        ...init,
        redirect: "error",
        cache: "no-store",
        credentials: "omit",
        signal: controller.signal,
      });
    } catch (error) {
      if (error instanceof InternalAuthApiError) throw error;
      throw new InternalAuthApiError(controller.signal.aborted ? 504 : 503, controller.signal.aborted ? "TIMEOUT" : "UNAVAILABLE");
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    async login(input: InternalLoginRequest) {
      const parsed = InternalLoginRequestSchema.safeParse(input);
      if (!parsed.success) throw new InternalAuthApiError(422, "INVALID_INPUT");
      const response = await execute({
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Request-ID": randomUUID(),
        },
        body: JSON.stringify(parsed.data),
      });
      if (!response.ok) {
        await response.body?.cancel();
        throw mappedError(response);
      }
      if (!response.headers.get("content-type")?.includes("application/json")) {
        await response.body?.cancel();
        throw new InternalAuthApiError(502, "INVALID_RESPONSE");
      }
      const result = sessionResponse.safeParse(await boundedJson(response));
      if (!result.success || Date.parse(result.data.absolute_expires_at) <= clock()) {
        throw new InternalAuthApiError(502, "INVALID_RESPONSE");
      }
      return result.data;
    },

    async logout(sessionToken: string, csrfToken: string) {
      const response = await execute({
        method: "DELETE",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${sessionToken}`,
          "X-CSRF-Token": csrfToken,
          "X-Request-ID": randomUUID(),
        },
      });
      if (response.status === 204) return;
      await response.body?.cancel();
      throw mappedError(response);
    },
  };
}
