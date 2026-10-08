import { describe, expect, it } from "vitest";
import { DashboardSummaryResponseSchema } from "../src/lib/server/api/contracts.generated";
import { configuredDashboardProfile, hasDashboardData, parseDashboardUrlQuery } from "../src/lib/dashboard/query";

const profileId = "c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4";
const snapshot = {
  processes_total: 1, current_candidate: 1, current_pending: 0, current_discarded: 0,
  needs_review: 1, selected: 0, human_pending: 0, human_discarded: 0, stale_reviews: 0,
  documents_total: 2, documents_with_artifact: 1, documents_with_text: 1,
};
const activity = {
  records_collected: 7, processes_first_seen: 1, documents_discovered: 2,
  document_screenings_total: 1, operational_resolutions_total: 1, human_reviews_total: 0,
  rounds_total: 2, rounds_success: 1, rounds_partial: 1, rounds_failed: 0,
};
const funnel = {
  records_collected: 7, unique_processes: 1, initial_candidate: 1, initial_pending: 0,
  initial_discarded: 0, document_evaluated: 1, operational_candidate: 1,
  operational_pending: 0, operational_discarded: 0, selected: 0, human_pending: 0, human_discarded: 0,
};
const summary = {
  profile_id: profileId,
  period: { from_datetime: null, to_datetime: null },
  current_snapshot: snapshot,
  period_activity: activity,
  funnel,
  source_coverage: [{ source: "FONTE-NOVA", rounds: 2, successful_rounds: 1, partial_rounds: 1, failed_rounds: 0, records_collected: 7, unique_processes: 1 }],
};

describe("dashboard contract and URL", () => {
  it("accepts every real block, nullable period bounds and an unknown source", () => {
    const parsed = DashboardSummaryResponseSchema.parse(summary);
    expect(parsed.period).toEqual({ from_datetime: null, to_datetime: null });
    expect(parsed.source_coverage[0]?.source).toBe("FONTE-NOVA");
  });

  it.each(["profile_id", "current_snapshot", "period_activity", "funnel", "source_coverage"])("requires %s", field => {
    const incomplete = { ...summary } as Record<string, unknown>;
    delete incomplete[field];
    expect(DashboardSummaryResponseSchema.safeParse(incomplete).success).toBe(false);
  });

  it.each([
    {},
    { from_datetime: "2026-10-01T00:00:00Z" },
    { to_datetime: "2026-10-02T00:00:00-03:00" },
    { from_datetime: "2026-10-01T00:00:00Z", to_datetime: "2026-10-02T00:00:00Z" },
  ])("accepts an empty, partial or complete period: %j", query => {
    expect(parseDashboardUrlQuery(query).success).toBe(true);
  });

  it.each([
    { from_datetime: "2026-10-01T00:00:00" },
    { from_datetime: "2026-10-02T00:00:00Z", to_datetime: "2026-10-01T00:00:00Z" },
    { from_datetime: ["2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z"] },
    { profile_id: profileId },
    { unexpected: "value" },
  ])("rejects unsafe or unsupported URL parameters: %j", query => {
    expect(parseDashboardUrlQuery(query).success).toBe(false);
  });

  it("requires exactly one valid server-side profile", () => {
    expect(configuredDashboardProfile({}).success).toBe(false);
    expect(configuredDashboardProfile({ API_PROFILE_ID: "invalid" }).success).toBe(false);
    expect(configuredDashboardProfile({ API_PROFILE_ID: profileId, API_PROFILE_CODE: "USIAR" }).success).toBe(false);
    expect(configuredDashboardProfile({ API_PROFILE_ID: profileId })).toMatchObject({ success: true, data: { profile_id: profileId } });
    expect(configuredDashboardProfile({ API_PROFILE_CODE: "USIAR" })).toMatchObject({ success: true, data: { profile_code: "USIAR" } });
  });

  it("recognizes only a genuinely empty API summary as empty", () => {
    expect(hasDashboardData(summary)).toBe(true);
    const zero = DashboardSummaryResponseSchema.parse({
      ...summary,
      current_snapshot: Object.fromEntries(Object.keys(snapshot).map(key => [key, 0])),
      period_activity: Object.fromEntries(Object.keys(activity).map(key => [key, 0])),
      funnel: Object.fromEntries(Object.keys(funnel).map(key => [key, 0])),
      source_coverage: [],
    });
    expect(hasDashboardData(zero)).toBe(false);
  });
});
