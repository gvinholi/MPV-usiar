import { describe, expect, it } from "vitest";
import {
  ErrorResponseSchema,
  OpportunityListItemResponseSchema,
  ReviewCreateRequestSchema,
  pageSchema,
} from "../src/lib/server/api/contracts.generated";

const review = {
  operational_resolution_id: "c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4",
  decision: "SELECTED",
  reason: "RELEVANT_SCOPE_CONFIRMED",
  idempotency_key: "review-1",
};

describe("generated FastAPI contracts", () => {
  it("accepts an omitted optional field and applies its null default", () => {
    const parsed = ErrorResponseSchema.parse({ error: { code: "NOT_FOUND", message: "Ausente." } });
    expect(parsed.error.details).toBeNull();
  });

  it("accepts explicit null for a nullable optional field", () => {
    expect(ErrorResponseSchema.parse({
      error: { code: "NOT_FOUND", message: "Ausente.", details: null },
    }).error.details).toBeNull();
  });

  it("preserves scalar and nullable defaults from Pydantic fields", () => {
    expect(ReviewCreateRequestSchema.parse(review)).toMatchObject({ comment: null, allow_stale: false });
  });

  it("keeps fields without defaults required even when they are nullable", () => {
    const item = {
      process_id: review.operational_resolution_id,
      source: null,
      official_id: null,
      description_preview: null,
      organization_name: null,
      organization_cnpj: null,
      municipality_name: null,
      uf: null,
      modality: null,
      estimated_value: null,
      publication_at: null,
      proposal_deadline_at: null,
      official_url: null,
      operational_resolution_id: null,
      operational_state: null,
      operational_reason: null,
      operational_resolved_at: null,
      human_review_status: "UNREVIEWED",
      human_decision: null,
      human_reason: null,
      reviewed_at: null,
      documents_count: 0,
      has_text: false,
      has_document_screening: false,
      latest_capture_at: null,
    };
    expect(OpportunityListItemResponseSchema.safeParse(item).success).toBe(true);
    const withoutRequiredNullable = Object.fromEntries(
      Object.entries(item).filter(([key]) => key !== "source"),
    );
    expect(OpportunityListItemResponseSchema.safeParse(withoutRequiredNullable).success).toBe(false);
  });

  it.each([
    { error: { code: "NOT_FOUND", message: "Ausente.", unexpected: true } },
    { error: { code: "NOT_FOUND", message: "Ausente." }, unexpected: true },
  ])("rejects extras wherever FastAPI inherits extra=forbid", payload => {
    expect(ErrorResponseSchema.safeParse(payload).success).toBe(false);
  });

  it("makes the generic page contract strict as well", () => {
    const schema = pageSchema(OpportunityListItemResponseSchema);
    expect(schema.safeParse({
      items: [],
      pagination: { page: 1, page_size: 25, total_items: 0, total_pages: 0 },
      unexpected: true,
    }).success).toBe(false);
  });

  it("preserves Field string constraints", () => {
    expect(ReviewCreateRequestSchema.safeParse({ ...review, idempotency_key: "" }).success).toBe(false);
    expect(ReviewCreateRequestSchema.safeParse({ ...review, comment: "x".repeat(4001) }).success).toBe(false);
  });
});
