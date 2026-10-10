import "server-only";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { Environment } from "../env";
import * as c from "./contracts";
import { ApiError, httpError } from "./errors";

type Query = Record<string, string | number | boolean | undefined>;
export type BearerCredential = {
  read(): Promise<string | undefined>;
  invalidate(): Promise<void>;
};
function validate<T extends z.ZodType>(schema: T, value: unknown): z.output<T> {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError("VALIDATION_ERROR", 422);
  return result.data;
}
async function boundedJson(response: Response) {
  const reader = response.body?.getReader();
  if (!reader) throw new ApiError("INVALID_RESPONSE", 502);
  let size = 0; const parts: Uint8Array[] = [];
  try {
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > 4 * 1024 * 1024) { await reader.cancel(); throw new ApiError("INVALID_RESPONSE", 502); }
      parts.push(chunk.value);
    }
  } finally { reader.releaseLock(); }
  try { return JSON.parse(Buffer.concat(parts).toString("utf8")) as unknown; }
  catch { throw new ApiError("INVALID_RESPONSE", 502); }
}

/** Only named read operations are exposed. Callers cannot choose a target or headers. */
export function createApiClient(env: Environment, credential: BearerCredential, transport: typeof fetch = fetch) {
  async function get<T extends z.ZodType>(path: string, schema: T, query: Query = {}): Promise<z.output<T>> {
    const accessToken = await credential.read();
    if (!accessToken) throw new ApiError("UNAUTHENTICATED", 401);
    const url = new URL(path, env.FASTAPI_BASE_URL);
    if (url.origin !== env.FASTAPI_BASE_URL) throw new ApiError("INVALID_RESPONSE", 502);
    for (const [name, value] of Object.entries(query)) if (value !== undefined) url.searchParams.set(name, String(value));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), env.API_TIMEOUT_MS);
    const requestId = randomUUID();
    try {
      const response = await transport(url, { method: "GET", redirect: "error", cache: "no-store", credentials: "omit",
        headers: { Authorization: `Bearer ${accessToken}`, Accept: "application/json", "X-Request-ID": requestId }, signal: controller.signal });
      if (!response.ok) {
        if (response.status === 401) await credential.invalidate();
        // Only conflict codes are inspected; no upstream messages/headers are forwarded.
        const body = response.status === 409 ? await boundedJson(response).catch(() => undefined) : undefined;
        if (response.status !== 409) await response.body?.cancel();
        throw httpError(response.status, body, requestId);
      }
      if (!response.headers.get("content-type")?.includes("application/json")) throw new ApiError("INVALID_RESPONSE", 502, requestId);
      const parsed = schema.safeParse(await boundedJson(response));
      if (!parsed.success) throw new ApiError("INVALID_RESPONSE", 502, requestId);
      return parsed.data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(controller.signal.aborted ? "TIMEOUT" : "NETWORK_ERROR", controller.signal.aborted ? 504 : 502, requestId);
    } finally { clearTimeout(timer); }
  }
  const processPath = (id: string) => `/api/v1/opportunities/${validate(z.uuid(), id)}`;
  return {
    ready: () => get("/ready", c.HealthResponseSchema),
    getDashboardSummary: (query: c.SummaryQuery) => get("/api/v1/dashboard/summary", c.DashboardSummaryResponseSchema, validate(c.summaryQuery, query)),
    listOpportunities: (query: c.OpportunitiesQuery) => get("/api/v1/opportunities", c.pageSchema(c.OpportunityListItemResponseSchema), validate(c.opportunitiesQuery, query)),
    getOpportunity: (id: string, profile: c.Profile) => get(processPath(id), c.OpportunityDetailResponseSchema, validate(c.profileSchema, profile)),
    getOpportunityBySource: (source: "PNCP" | "RHS", officialId: string, profile: c.Profile) => get("/api/v1/opportunities/by-source", c.OpportunityDetailResponseSchema,
      { ...validate(c.profileSchema, profile), source: validate(z.enum(["PNCP", "RHS"]), source), official_id: validate(z.string().trim().min(1), officialId) }),
    listDocuments: (id: string, page: c.Pagination = {}) => get(`${processPath(id)}/documents`, c.pageSchema(c.OpportunityDocumentResponseSchema), validate(c.paginationSchema, page)),
    listEvidence: (id: string, profile: c.Profile, page: c.Pagination = {}) => get(`${processPath(id)}/document-evidence`, c.pageSchema(c.DocumentEvidenceResponseSchema),
      { ...validate(c.profileSchema, profile), ...validate(c.paginationSchema, page) }),
    listTimeline: (id: string, profile: c.Profile, page: c.Pagination = {}) => get(`${processPath(id)}/timeline`, c.pageSchema(c.TimelineItemResponseSchema),
      { ...validate(c.profileSchema, profile), ...validate(c.paginationSchema, page) }),
    listReviewQueue: (query: c.QueueQuery) => get("/api/v1/review-queue", c.pageSchema(c.DashboardReviewQueueItemResponseSchema), validate(c.queueQuery, query)),
    listCollectionRounds: (query: c.RoundsQuery = {}) => get("/api/v1/collection-rounds", c.pageSchema(c.CollectionRoundListItemResponseSchema), validate(c.roundsQuery, query)),
    getCollectionRound: (id: string) => get(`/api/v1/collection-rounds/${validate(z.uuid(), id)}`, c.CollectionRoundDetailResponseSchema),
  };
}
