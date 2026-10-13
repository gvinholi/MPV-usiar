import "server-only";
import { z } from "zod";
import { HumanReviewDecisionSchema, HumanReviewStatusSchema, ReviewQueueSchema } from "./contracts.generated";
export * from "./contracts.generated";

const text = z.string().min(1).max(300).refine(v => v.trim().length > 0);
const date = z.iso.datetime({ offset: true });
export const profileFields = { profile_id: z.uuid().optional(), profile_code: text.optional() };
function oneProfile(v: { profile_id?: string; profile_code?: string }) { return Boolean(v.profile_id) !== Boolean(v.profile_code); }
export const profileSchema = z.object(profileFields).strict().refine(oneProfile, "Informe exatamente um perfil.");
export type Profile = z.infer<typeof profileSchema>;
const paginationFields = {
  page: z.number().int().min(1).default(1), page_size: z.number().int().min(1).max(100).default(25),
};
export const paginationSchema = z.object(paginationFields).strict();
export type Pagination = z.input<typeof paginationSchema>;
const sortFields = {
  sort: z.enum(["publication_at", "proposal_deadline_at", "estimated_value", "latest_capture_at", "operational_resolved_at", "reviewed_at"]).default("latest_capture_at"),
  direction: z.enum(["ASC", "DESC"]).default("DESC"),
};
const periodFields = { from_datetime: date.optional(), to_datetime: date.optional() };
function ordered(start?: string, end?: string) { return !start || !end || Date.parse(start) < Date.parse(end); }
export const summaryQuery = z.object({ ...profileFields, ...periodFields }).strict().refine(oneProfile)
  .refine(v => ordered(v.from_datetime, v.to_datetime));
export type SummaryQuery = z.input<typeof summaryQuery>;
const operationalState = z.enum(["CANDIDATE", "PENDING", "DISCARDED"]);
export const opportunitiesQuery = z.object({
  ...profileFields, ...paginationFields, ...sortFields,
  operational_state: z.union([
    operationalState,
    z.array(operationalState).min(1).max(3).refine(value => new Set(value).size === value.length),
  ]).optional(),
  human_review_status: HumanReviewStatusSchema.optional(), human_decision: HumanReviewDecisionSchema.optional(),
  source: z.enum(["PNCP", "RHS"]).optional(), uf: z.string().regex(/^[a-zA-Z]{2}$/).transform(v => v.toUpperCase()).optional(),
  municipality: text.optional(), modality: text.optional(), search: text.optional(),
  publication_from: date.optional(), publication_to: date.optional(),
  proposal_deadline_from: date.optional(), proposal_deadline_to: date.optional(),
  captured_from: date.optional(), captured_to: date.optional(),
  has_documents: z.boolean().optional(), has_text: z.boolean().optional(), has_document_screening: z.boolean().optional(),
  review_queue: ReviewQueueSchema.optional(),
}).strict().refine(oneProfile).refine(v => ordered(v.publication_from, v.publication_to) &&
  ordered(v.proposal_deadline_from, v.proposal_deadline_to) && ordered(v.captured_from, v.captured_to));
export type OpportunitiesQuery = z.input<typeof opportunitiesQuery>;
export const queueQuery = z.object({ ...profileFields, ...paginationFields, ...sortFields,
  queue: ReviewQueueSchema.default("NEEDS_REVIEW"),
}).strict().refine(oneProfile);
export type QueueQuery = z.input<typeof queueQuery>;
export const roundsQuery = z.object({ ...paginationFields, ...periodFields, source: z.enum(["PNCP", "RHS"]).optional() })
  .strict().refine(v => ordered(v.from_datetime, v.to_datetime));
export type RoundsQuery = z.input<typeof roundsQuery>;
