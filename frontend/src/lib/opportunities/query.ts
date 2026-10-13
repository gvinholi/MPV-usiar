import { z } from "zod";

export const USIAR_V2_PROFILE_ID = "42227c23-f6ea-5a43-b640-56ed6eb6981c";
export const OPPORTUNITIES_PAGE_SIZE = 25;

const filterSchema = z.enum(["all", "candidate", "pending"]);
const pageSchema = z.string().regex(/^[1-9]\d{0,5}$/).transform(Number).default(1);
const querySchema = z.object({
  state: filterSchema.default("all"),
  page: pageSchema,
}).strict();

export type OpportunityFilter = z.infer<typeof filterSchema>;
export type RawOpportunitySearchParams = Record<string, string | string[] | undefined>;

export function parseOpportunitiesUrlQuery(value: RawOpportunitySearchParams) {
  return querySchema.safeParse(value);
}

export function configuredUsiarV2Profile(value: { API_PROFILE_ID?: string; API_PROFILE_CODE?: string }) {
  if (value.API_PROFILE_ID !== USIAR_V2_PROFILE_ID || value.API_PROFILE_CODE) return undefined;
  return { profile_id: USIAR_V2_PROFILE_ID } as const;
}

export function operationalStates(filter: OpportunityFilter): ("CANDIDATE" | "PENDING")[] {
  if (filter === "candidate") return ["CANDIDATE"];
  if (filter === "pending") return ["PENDING"];
  return ["CANDIDATE", "PENDING"];
}

export function opportunitiesHref(filter: OpportunityFilter, page = 1) {
  const params = new URLSearchParams();
  if (filter !== "all") params.set("state", filter);
  if (page > 1) params.set("page", String(page));
  return params.size ? `/opportunities?${params}` : "/opportunities";
}

export function publicationParts(value: string | null) {
  if (!value) return { date: "—", hour: "—" };
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match) return { date: "—", hour: "—" };
  return { date: `${match[3]}/${match[2]}/${match[1]}`, hour: match[4] };
}

export function formatBrl(value: string | null) {
  if (value === null) return "—";
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return "—";
  const negative = match[1] === "-";
  const fraction = (match[3] ?? "").padEnd(3, "0");
  let cents = BigInt(match[2]!) * 100n + BigInt(fraction.slice(0, 2));
  if (fraction[2]! >= "5") cents += 1n;
  const whole = (cents / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const decimals = (cents % 100n).toString().padStart(2, "0");
  const sign = negative && cents !== 0n ? "-" : "";
  return `${sign}R$ ${whole},${decimals}`;
}

export function safeOfficialUrl(value: string | null) {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
    return url.href;
  } catch {
    return undefined;
  }
}
