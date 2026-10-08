import { z } from "zod";
import type { DashboardSummaryResponse } from "@/lib/server/api/contracts.generated";

const awareDate = z.iso.datetime({ offset: true });

export const dashboardUrlQuerySchema = z.object({
  from_datetime: awareDate.optional(),
  to_datetime: awareDate.optional(),
}).strict().refine(
  value => !value.from_datetime || !value.to_datetime || Date.parse(value.from_datetime) < Date.parse(value.to_datetime),
  { message: "O início deve ser anterior ao fim." },
);

export type DashboardUrlQuery = z.infer<typeof dashboardUrlQuerySchema>;
export type RawSearchParams = Record<string, string | string[] | undefined>;

export function parseDashboardUrlQuery(value: RawSearchParams) {
  return dashboardUrlQuerySchema.safeParse(value);
}

const configuredProfileSchema = z.object({
  profile_id: z.uuid().optional(),
  profile_code: z.string().trim().min(1).max(300).optional(),
}).strict().refine(value => Boolean(value.profile_id) !== Boolean(value.profile_code));

export function configuredDashboardProfile(value: { API_PROFILE_ID?: string; API_PROFILE_CODE?: string }) {
  const candidate = {
    profile_id: value.API_PROFILE_ID,
    profile_code: value.API_PROFILE_CODE,
  };
  return configuredProfileSchema.safeParse(candidate);
}

export function hasDashboardData(summary: DashboardSummaryResponse) {
  return summary.source_coverage.length > 0 ||
    Object.values(summary.current_snapshot).some(value => value !== 0) ||
    Object.values(summary.period_activity).some(value => value !== 0) ||
    Object.values(summary.funnel).some(value => value !== 0);
}
