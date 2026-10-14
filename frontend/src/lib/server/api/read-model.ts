import "server-only";
import { isIP } from "node:net";
import type { Client } from "pg";
import { withDatabase, jsonRows } from "../db";
import { ApiError } from "./errors";
import type * as C from "./contracts";

async function profileId(db: Client, query: { profile_id?: string; profile_code?: string }) {
  if (query.profile_id) {
    const found = await db.query("SELECT id FROM screening_profiles WHERE id=$1", [query.profile_id]);
    if (!found.rowCount) throw new ApiError("NOT_FOUND", 404);
    return query.profile_id;
  }
  const found = await db.query("SELECT id FROM screening_profiles WHERE code=$1 ORDER BY created_at DESC", [query.profile_code]);
  if (!found.rowCount) throw new ApiError("NOT_FOUND", 404);
  if ((found.rowCount ?? 0) > 1) throw new ApiError("AMBIGUOUS_PROFILE", 409);
  return String(found.rows[0].id);
}

const BASE = `
WITH observations AS (
 SELECT o.*, row_number() OVER (PARTITION BY process_id ORDER BY captured_at DESC NULLS LAST, created_at DESC, id DESC) rn FROM process_observations o
), current_evaluations AS (
 SELECT e.* FROM screening_evaluations e JOIN observations o ON o.id=e.observation_id AND o.rn=1 WHERE e.profile_id=$1
), resolutions AS (
 -- Current when its initial evaluation is the latest observation's evaluation or logically
 -- equivalent to it (engine, state, reason, evidence): an identical re-collection keeps the
 -- existing resolution, whose fingerprint already covers that content.
 SELECT r.*, row_number() OVER (PARTITION BY r.process_id,r.profile_id ORDER BY r.resolved_at DESC,r.created_at DESC,r.resolution_fingerprint DESC) rn
 FROM operational_resolutions r JOIN screening_evaluations e ON e.id=r.initial_evaluation_id
 WHERE r.profile_id=$1 AND EXISTS(SELECT 1 FROM current_evaluations c WHERE c.process_id=r.process_id AND (c.id=e.id OR (
  c.engine_version=e.engine_version AND c.state=e.state AND c.reason_code=e.reason_code
  AND (SELECT string_agg(format('%L,%L,%L,%L',x.category,x.configured_term,x.field,x.matched_text),';' ORDER BY x.category,x.configured_term,x.field,x.matched_text) FROM screening_evidence x WHERE x.evaluation_id=c.id)
   IS NOT DISTINCT FROM (SELECT string_agg(format('%L,%L,%L,%L',x.category,x.configured_term,x.field,x.matched_text),';' ORDER BY x.category,x.configured_term,x.field,x.matched_text) FROM screening_evidence x WHERE x.evaluation_id=e.id))))
), reviews AS (
 SELECT h.*, row_number() OVER (PARTITION BY operational_resolution_id ORDER BY decided_at DESC,created_at DESC,sequence DESC) rn FROM human_reviews h
), acquisitions AS (
 SELECT a.*,row_number() OVER (PARTITION BY document_id ORDER BY acquired_at DESC,created_at DESC,id DESC) rn FROM document_artifacts a
), extractions AS (
 SELECT e.*,row_number() OVER (PARTITION BY source_id ORDER BY finished_at DESC,created_at DESC,extractor_name DESC,extractor_version DESC,id DESC) rn FROM text_extractions e
), document_flags AS (
 SELECT d.id,d.process_id,d.first_seen_at,a.artifact_id,
 EXISTS(SELECT 1 FROM artifact_text_sources s JOIN extractions e ON e.source_id=s.id AND e.rn=1
        WHERE s.artifact_id=a.artifact_id AND e.pages_with_text>0) has_text
 FROM process_documents d LEFT JOIN acquisitions a ON a.document_id=d.id AND a.rn=1
), document_counts AS (
 SELECT process_id,count(*)::int documents_count,bool_or(has_text) has_text,
 count(*) FILTER(WHERE artifact_id IS NOT NULL)::int documents_with_artifact,
 count(*) FILTER(WHERE has_text)::int documents_with_text
 FROM document_flags GROUP BY process_id
), base AS (
 SELECT p.id process_id,p.created_at first_seen_at,o.source,si.official_id,o.description,left(o.description,300) description_preview,o.organization_name,o.organization_cnpj,
 o.locality municipality_name,o.state uf,o.modality,o.estimated_value::text,o.published_at publication_at,o.closes_at proposal_deadline_at,
 o.official_url,o.notice_number,r.id operational_resolution_id,r.state operational_state,r.reason_code operational_reason,r.resolved_at operational_resolved_at,
 CASE WHEN h.id IS NOT NULL THEN 'REVIEWED' WHEN EXISTS(SELECT 1 FROM human_reviews hx JOIN operational_resolutions rx ON rx.id=hx.operational_resolution_id WHERE rx.process_id=p.id AND rx.profile_id=$1) THEN 'STALE' ELSE 'UNREVIEWED' END human_review_status,
 h.decision human_decision,h.reason_code human_reason,h.decided_at reviewed_at,coalesce(d.documents_count,0)::int documents_count,
 coalesce(d.has_text,false) has_text,coalesce(d.documents_with_artifact,0)::int documents_with_artifact,
 coalesce(d.documents_with_text,0)::int documents_with_text,o.id observation_id,
 EXISTS(SELECT 1 FROM document_screening_evaluations de WHERE de.process_id=p.id AND de.profile_id=$1) has_document_screening,
 o.captured_at latest_capture_at,CASE WHEN o.source='RHS' THEN si.official_id END rhs_id,NULL::text monthly_value
 FROM processes p LEFT JOIN observations o ON o.process_id=p.id AND o.rn=1
 LEFT JOIN LATERAL(SELECT official_id FROM source_identities x WHERE x.process_id=p.id AND x.source=o.source ORDER BY official_id LIMIT 1) si ON true
 LEFT JOIN resolutions r ON r.process_id=p.id AND r.rn=1 LEFT JOIN reviews h ON h.operational_resolution_id=r.id AND h.rn=1 LEFT JOIN document_counts d ON d.process_id=p.id
)`;

const LIST_COLUMNS = [
  "process_id", "source", "official_id", "description_preview", "organization_name", "organization_cnpj",
  "municipality_name", "uf", "modality", "estimated_value", "publication_at", "proposal_deadline_at",
  "official_url", "notice_number", "operational_resolution_id", "operational_state", "operational_reason",
  "operational_resolved_at", "human_review_status", "human_decision", "human_reason", "reviewed_at",
  "documents_count", "has_text", "has_document_screening", "latest_capture_at", "rhs_id", "monthly_value",
].join(",");

const SENSITIVE_QUERY_NAMES = new Set([
  "access_token", "api_key", "apikey", "auth", "authorization", "chave", "code", "credential",
  "id_token", "jwt", "key", "password", "passwd", "secret", "session", "sig", "signature", "token",
  "x_amz_credential", "x_amz_signature", "x_goog_credential", "x_goog_signature",
]);
export function publicUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value || value !== value.trim() || value.length > 2048 || /[\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const parsed = new URL(value); const host = parsed.hostname.toLowerCase(); const unwrappedHost = host.replace(/^\[|\]$/g, "");
    if (!["http:", "https:"].includes(parsed.protocol) || !host || parsed.username || parsed.password || parsed.hash) return null;
    if (host === "localhost" || !host.includes(".") || host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".localhost")) return null;
    // Official links currently use DNS names. Reject every IP literal rather than
    // risk exposing a private/special address through the read model.
    if (isIP(unwrappedHost)) return null;
    const queryNames = [...parsed.searchParams.keys()]; if (queryNames.length > 50) return null;
    for (const name of queryNames) {
      const normalized = name.toLowerCase().replaceAll("-", "_");
      if (SENSITIVE_QUERY_NAMES.has(normalized) || ["credential", "password", "secret", "signature", "token"].some((part) => normalized.includes(part))) return null;
    }
    return value;
  } catch { return null; }
}

function opportunityFilters(query: C.OpportunitiesQuery, values: unknown[]) {
  const clauses: string[] = [];
  const add = (sql: string, value: unknown) => { values.push(value); clauses.push(sql.replace("?", `$${values.length}`)); };
  const states = Array.isArray(query.operational_state) ? query.operational_state : query.operational_state ? [query.operational_state] : undefined;
  if (states) add("operational_state=ANY(?::text[])", states);
  if (query.source) add("EXISTS(SELECT 1 FROM source_identities sx WHERE sx.process_id=base.process_id AND sx.source=?)", query.source);
  for (const [key, column] of [["uf","uf"],["municipality","municipality_name"],["modality","modality"]] as const) {
    const value = query[key]; if (value) add(`${column}=?`, value);
  }
  if (query.human_review_status) add("human_review_status=?", query.human_review_status);
  if (query.human_decision) add("human_decision=?", query.human_decision);
  if (query.search) add("description ILIKE '%' || replace(replace(replace(?, '!', '!!'), '%', '!%'), '_', '!_') || '%' ESCAPE '!'", query.search);
  const ranges = [["publication_from","publication_at",">="],["publication_to","publication_at","<"],["proposal_deadline_from","proposal_deadline_at",">="],["proposal_deadline_to","proposal_deadline_at","<"],["captured_from","latest_capture_at",">="],["captured_to","latest_capture_at","<"]] as const;
  for (const [key,column,operator] of ranges) if (query[key]) add(`${column}${operator}?`, query[key]);
  if (query.has_documents !== undefined) clauses.push(query.has_documents ? "documents_count>0" : "documents_count=0");
  if (query.has_text !== undefined) add("has_text=?", query.has_text);
  if (query.has_document_screening !== undefined) add("has_document_screening=?", query.has_document_screening);
  if (query.review_queue === "NEEDS_REVIEW") clauses.push("human_review_status<>'REVIEWED' AND operational_state<>'DISCARDED'");
  if (query.review_queue === "STALE_REVIEW") clauses.push("human_review_status='STALE'");
  if (query.review_queue === "SELECTED") clauses.push("human_decision='SELECTED'");
  if (query.review_queue === "HUMAN_PENDING") clauses.push("human_decision='PENDING'");
  if (query.review_queue === "HUMAN_DISCARDED") clauses.push("human_decision='DISCARDED'");
  return clauses.length ? clauses.join(" AND ") : "true";
}

export async function listOpportunities(query: C.OpportunitiesQuery): Promise<C.PageResponse<C.OpportunityListItemResponse>> {
  return withDatabase(async (db) => {
    const profile = await profileId(db, query); const values: unknown[] = [profile];
    const where = opportunityFilters(query, values); const count = await db.query(`${BASE} SELECT count(*)::int total FROM base WHERE ${where}`, values);
    const total = Number(count.rows[0].total); const page = query.page ?? 1; const size = query.page_size ?? 25;
    const sort = query.sort ?? "latest_capture_at"; const direction = query.direction ?? "DESC";
    values.push(size, (page - 1) * size);
    const rows = await db.query(`${BASE} SELECT ${LIST_COLUMNS} FROM base WHERE ${where} ORDER BY ${sort} ${direction} NULLS LAST,process_id ${direction} LIMIT $${values.length-1} OFFSET $${values.length}`, values);
    const items = jsonRows(rows.rows).map((row) => ({ ...row, official_url: publicUrl(row.official_url) })) as C.OpportunityListItemResponse[];
    return { items, pagination: { page, page_size: size, total_items: total, total_pages: total ? Math.ceil(total / size) : 0 } };
  });
}

export async function dashboardSummary(query: C.SummaryQuery): Promise<C.DashboardSummaryResponse> {
  return withDatabase(async (db) => {
    const profile = await profileId(db, query); const values: unknown[] = [profile];
    const fromIndex = query.from_datetime ? (values.push(query.from_datetime), values.length) : undefined;
    const toIndex = query.to_datetime ? (values.push(query.to_datetime), values.length) : undefined;
    const during = (column: string) => [
      fromIndex ? `${column}>=$${fromIndex}` : undefined,
      toIndex ? `${column}<$${toIndex}` : undefined,
    ].filter(Boolean).join(" AND ") || "true";
    const cohort = during("first_seen_at");
    const roundWhere = during("started_at");
    const current = await db.query(`${BASE} SELECT count(*)::int processes_total,count(*) FILTER(WHERE operational_state='CANDIDATE')::int current_candidate,count(*) FILTER(WHERE operational_state='PENDING')::int current_pending,count(*) FILTER(WHERE operational_state='DISCARDED')::int current_discarded,count(*) FILTER(WHERE human_review_status<>'REVIEWED' AND operational_state<>'DISCARDED')::int needs_review,count(*) FILTER(WHERE human_decision='SELECTED')::int selected,count(*) FILTER(WHERE human_decision='PENDING')::int human_pending,count(*) FILTER(WHERE human_decision='DISCARDED')::int human_discarded,count(*) FILTER(WHERE human_review_status='STALE')::int stale_reviews,coalesce(sum(documents_count),0)::int documents_total,coalesce(sum(documents_with_artifact),0)::int documents_with_artifact,coalesce(sum(documents_with_text),0)::int documents_with_text FROM base WHERE ${cohort}`, values);
    const activity = await db.query(`SELECT
      (SELECT coalesce(sum(records_collected),0)::int FROM collection_rounds WHERE ${roundWhere}) records_collected,
      (SELECT count(*)::int FROM processes WHERE ${during("created_at")}) processes_first_seen,
      (SELECT count(*)::int FROM process_documents WHERE ${during("first_seen_at")}) documents_discovered,
      (SELECT count(*)::int FROM document_screening_evaluations WHERE profile_id=$1 AND ${during("evaluated_at")}) document_screenings_total,
      (SELECT count(*)::int FROM operational_resolutions WHERE profile_id=$1 AND ${during("resolved_at")}) operational_resolutions_total,
      (SELECT count(*)::int FROM human_reviews h JOIN operational_resolutions r ON r.id=h.operational_resolution_id WHERE r.profile_id=$1 AND ${during("h.decided_at")}) human_reviews_total,
      count(*)::int rounds_total,count(*) FILTER(WHERE status='SUCCESS')::int rounds_success,
      count(*) FILTER(WHERE status='PARTIAL')::int rounds_partial,count(*) FILTER(WHERE status='FAILED')::int rounds_failed
      FROM collection_rounds WHERE ${roundWhere}`, values);
    const funnel = await db.query(`${BASE}, initial AS (
      SELECT e.*,row_number() OVER(PARTITION BY e.process_id ORDER BY e.evaluated_at DESC,e.created_at DESC,e.engine_version DESC,e.id DESC) rn
      FROM screening_evaluations e JOIN base current_b ON current_b.process_id=e.process_id AND current_b.observation_id=e.observation_id
      WHERE e.profile_id=$1
    ) SELECT (SELECT coalesce(sum(records_collected),0)::int FROM collection_rounds WHERE ${roundWhere}) records_collected,
      count(*)::int unique_processes,count(*) FILTER(WHERE i.state='CANDIDATE')::int initial_candidate,
      count(*) FILTER(WHERE i.state='PENDING')::int initial_pending,count(*) FILTER(WHERE i.state='DISCARDED')::int initial_discarded,
      count(*) FILTER(WHERE b.has_document_screening)::int document_evaluated,
      count(*) FILTER(WHERE b.operational_state='CANDIDATE')::int operational_candidate,
      count(*) FILTER(WHERE b.operational_state='PENDING')::int operational_pending,
      count(*) FILTER(WHERE b.operational_state='DISCARDED')::int operational_discarded,
      count(*) FILTER(WHERE b.human_decision='SELECTED')::int selected,
      count(*) FILTER(WHERE b.human_decision='PENDING')::int human_pending,
      count(*) FILTER(WHERE b.human_decision='DISCARDED')::int human_discarded
      FROM base b LEFT JOIN initial i ON i.process_id=b.process_id AND i.rn=1 WHERE ${cohort}`, values);
    const coverage = await db.query(`WITH scoped AS(SELECT * FROM collection_rounds WHERE ${roundWhere} AND $1::uuid IS NOT NULL)
      SELECT r.source,count(*)::int rounds,count(*) FILTER(WHERE status='SUCCESS')::int successful_rounds,
      count(*) FILTER(WHERE status='PARTIAL')::int partial_rounds,count(*) FILTER(WHERE status='FAILED')::int failed_rounds,
      coalesce(sum(records_collected),0)::int records_collected,
      (SELECT count(DISTINCT o.process_id)::int FROM process_observations o JOIN scoped sr ON sr.id=o.round_id WHERE sr.source=r.source) unique_processes
      FROM scoped r GROUP BY r.source ORDER BY r.source`, values);
    return { profile_id: profile, period: { from_datetime: query.from_datetime ?? null, to_datetime: query.to_datetime ?? null }, current_snapshot: jsonRows(current.rows)[0] as C.CurrentSnapshotResponse, period_activity: jsonRows(activity.rows)[0] as C.PeriodActivityResponse, funnel: jsonRows(funnel.rows)[0] as C.PilotFunnelResponse, source_coverage: jsonRows(coverage.rows) as C.SourceCoverageResponse[] };
  });
}
