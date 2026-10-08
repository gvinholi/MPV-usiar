import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "../src/lib/server/api/client";
import { ApiError } from "../src/lib/server/api/errors";
import { opportunitiesQuery, summaryQuery } from "../src/lib/server/api/contracts";
import { apiFixture } from "./helpers";

const id = "c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4";
const item = {
  process_id: id, source: "PNCP", official_id: "123/2026/1", description_preview: "Manutenção",
  organization_name: null, organization_cnpj: null, municipality_name: null, uf: null, modality: null,
  estimated_value: "12345678901234567890.12", publication_at: "2026-10-01T12:00:00-03:00", proposal_deadline_at: null,
  official_url: null, operational_resolution_id: null, operational_state: null, operational_reason: null, operational_resolved_at: null,
  human_review_status: "UNREVIEWED", human_decision: null, human_reason: null, reviewed_at: null,
  documents_count: 0, has_text: false, has_document_screening: false, latest_capture_at: null,
};
const page = { items: [item], pagination: { page: 1, page_size: 25, total_items: 1, total_pages: 1 } };

describe("server-only HTTP client", () => {
  it("sends bearer exclusively to configured API, preserves decimals/date/null and encodes filters", async () => {
    const f = await apiFixture(); const transport = vi.fn(async () => Response.json(page));
    const api = createApiClient(f.env, f.store, f.id, transport);
    const result = await api.listOpportunities({ profile_code: "USIAR", search: "a&url=https://evil.test", has_text: false, uf: "sp" });
    expect(result.items[0]?.estimated_value).toBe(item.estimated_value);
    expect(result.items[0]?.publication_at).toBe(item.publication_at); expect(result.items[0]?.human_decision).toBeNull();
    const [url, options] = transport.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.origin).toBe(f.env.FASTAPI_BASE_URL); expect(url.searchParams.get("search")).toBe("a&url=https://evil.test");
    expect(url.searchParams.get("page_size")).toBe("25"); expect(url.searchParams.get("has_text")).toBe("false"); expect(url.searchParams.get("uf")).toBe("SP");
    expect(options).toMatchObject({ redirect: "error", credentials: "omit", cache: "no-store", method: "GET" });
    const headers = new Headers(options.headers);
    expect(headers.get("authorization")).toBe("Bearer test-only-access-token"); expect(headers.has("cookie")).toBe(false);
  });
  it.each([401, 403, 404, 409, 422, 500, 503])("normalizes %i without leaking upstream messages", async status => {
    const f = await apiFixture(); const transport = vi.fn(async () => Response.json({ error: { code: "SECRET", message: "test-only-access-token internal SQL password" } }, { status }));
    const api = createApiClient(f.env, f.store, f.id, transport);
    await expect(api.getDashboardSummary({ profile_code: "USIAR" })).rejects.toMatchObject({ status });
    try { await api.getDashboardSummary({ profile_code: "USIAR" }); } catch (error) {
      expect(error).toBeInstanceOf(ApiError); expect(String(error)).not.toMatch(/access-token|SQL|password/);
    }
    if (status === 401) expect(await f.store.readSession(f.id)).toBeUndefined();
    else expect(await f.store.readSession(f.id)).toBeDefined();
  });
  it.each(["AMBIGUOUS_PROFILE", "IDEMPOTENCY_CONFLICT", "STALE_OPERATIONAL_RESOLUTION"])("preserves known conflict code %s", async code => {
    const f = await apiFixture(); const api = createApiClient(f.env, f.store, f.id, async () => Response.json({ error: { code } }, { status: 409 }));
    await expect(api.getDashboardSummary({ profile_code: "USIAR" })).rejects.toMatchObject({ code });
  });
  it("requires a valid session before network access", async () => {
    const f = await apiFixture(); const transport = vi.fn(); await f.store.deleteSession(f.id);
    await expect(createApiClient(f.env, f.store, f.id, transport).ready()).rejects.toMatchObject({ status: 401 }); expect(transport).not.toHaveBeenCalled();
  });
  it("times out without leaking transport exceptions", async () => {
    const f = await apiFixture(); f.env.API_TIMEOUT_MS = 10;
    const transport: typeof fetch = (_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new Error("internal-secret")));
    });
    await expect(createApiClient(f.env, f.store, f.id, transport).getDashboardSummary({ profile_code: "USIAR" })).rejects.toMatchObject({ code: "TIMEOUT", status: 504 });
  });
  it("sanitizes network failures and incompatible JSON", async () => {
    const f = await apiFixture();
    await expect(createApiClient(f.env, f.store, f.id, async () => { throw new Error("token-secret"); }).ready()).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    await expect(createApiClient(f.env, f.store, f.id, async () => Response.json({ token: "secret" })).ready()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("rejects redirects without following them", async () => {
    const f = await apiFixture(); const transport = vi.fn(async () => new Response(null, { status: 302, headers: { Location: "https://evil.test" } }));
    await expect(createApiClient(f.env, f.store, f.id, transport).ready()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(transport).toHaveBeenCalledTimes(1);
  });
  it("validates ids and forbids arbitrary query keys before sending requests", async () => {
    const f = await apiFixture(); const transport = vi.fn(); const api = createApiClient(f.env, f.store, f.id, transport);
    expect(() => api.getCollectionRound("//evil.test")).toThrow();
    expect(() => api.listOpportunities({ profile_code: "USIAR", url: "https://evil.test" } as never)).toThrow();
    expect(transport).not.toHaveBeenCalled();
  });
  it("covers every named read resource without exposing a generic request method", async () => {
    const f = await apiFixture(); const transport = vi.fn(async () => Response.json({ error: {} }, { status: 404 }));
    const api = createApiClient(f.env, f.store, f.id, transport); const profile = { profile_code: "USIAR" };
    const operations = [
      () => api.getDashboardSummary(profile), () => api.getOpportunity(id, profile),
      () => api.getOpportunityBySource("PNCP", "123/2026/1", profile), () => api.listDocuments(id),
      () => api.listEvidence(id, profile), () => api.listTimeline(id, profile), () => api.listReviewQueue(profile),
      () => api.listCollectionRounds(), () => api.getCollectionRound(id),
    ];
    for (const operation of operations) await expect(operation()).rejects.toMatchObject({ status: 404 });
    expect(transport).toHaveBeenCalledTimes(operations.length); expect(api).not.toHaveProperty("get"); expect(api).not.toHaveProperty("post");
  });
});
describe("query contracts", () => {
  it.each([
    {}, { profile_code: "USIAR", profile_id: id }, { profile_code: "USIAR", page: 0 },
    { profile_code: "USIAR", page_size: 101 }, { profile_code: "USIAR", direction: "desc" },
    { profile_code: "USIAR", captured_from: "2026-10-01T10:00:00" },
    { profile_code: "USIAR", captured_from: "2026-10-02T00:00:00Z", captured_to: "2026-10-01T00:00:00Z" },
    { profile_code: "USIAR", include_operational_discarded: true },
  ])("rejects unsupported query %j", query => { expect(opportunitiesQuery.safeParse(query).success).toBe(false); });
  it("preserves timezone and half-open interval boundaries", () => {
    const query = { profile_code: "USIAR", from_datetime: "2026-10-01T00:00:00-03:00", to_datetime: "2026-10-02T00:00:00-03:00" };
    expect(summaryQuery.parse(query)).toEqual(query);
    expect(summaryQuery.safeParse({ ...query, to_datetime: query.from_datetime }).success).toBe(false);
  });
});
