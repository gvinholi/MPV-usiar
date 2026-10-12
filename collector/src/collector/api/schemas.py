"""Explicit and stable HTTP response contracts."""
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from collector.application.human_review.models import HumanReviewDecision, HumanReviewReason, HumanReviewStatus

class HttpModel(BaseModel): model_config = ConfigDict(extra="forbid")
class HealthResponse(HttpModel): status: str
class ErrorDetailResponse(HttpModel): field: str; message: str
class ErrorBodyResponse(HttpModel):
    code: str; message: str; details: list[ErrorDetailResponse] | None = None
class ErrorResponse(HttpModel): error: ErrorBodyResponse
class PaginationResponse(HttpModel): page: int; page_size: int; total_items: int; total_pages: int
T = TypeVar("T")
class PageResponse(HttpModel, Generic[T]): items: list[T]; pagination: PaginationResponse
class TimeRangeResponse(HttpModel): from_datetime: datetime | None; to_datetime: datetime | None

class SourceCoverageResponse(HttpModel):
    source: str; rounds: int; successful_rounds: int; partial_rounds: int; failed_rounds: int; records_collected: int; unique_processes: int
class CurrentSnapshotResponse(HttpModel):
    processes_total: int; current_candidate: int; current_pending: int; current_discarded: int; needs_review: int; selected: int; human_pending: int; human_discarded: int; stale_reviews: int; documents_total: int; documents_with_artifact: int; documents_with_text: int
class PeriodActivityResponse(HttpModel):
    records_collected: int; processes_first_seen: int; documents_discovered: int; document_screenings_total: int; operational_resolutions_total: int; human_reviews_total: int; rounds_total: int; rounds_success: int; rounds_partial: int; rounds_failed: int
class PilotFunnelResponse(HttpModel):
    records_collected: int; unique_processes: int; initial_candidate: int; initial_pending: int; initial_discarded: int; document_evaluated: int; operational_candidate: int; operational_pending: int; operational_discarded: int; selected: int; human_pending: int; human_discarded: int
class DashboardSummaryResponse(HttpModel):
    profile_id: UUID; period: TimeRangeResponse; current_snapshot: CurrentSnapshotResponse; period_activity: PeriodActivityResponse; funnel: PilotFunnelResponse; source_coverage: list[SourceCoverageResponse]

class OpportunityListItemResponse(HttpModel):
    process_id: UUID; source: str | None; official_id: str | None; description_preview: str | None; organization_name: str | None; organization_cnpj: str | None; municipality_name: str | None; uf: str | None; modality: str | None; estimated_value: str | None; publication_at: datetime | None; proposal_deadline_at: datetime | None; official_url: str | None; notice_number: str | None; operational_resolution_id: UUID | None; operational_state: str | None; operational_reason: str | None; operational_resolved_at: datetime | None; human_review_status: HumanReviewStatus; human_decision: HumanReviewDecision | None; human_reason: str | None; reviewed_at: datetime | None; documents_count: int; has_text: bool; has_document_screening: bool; latest_capture_at: datetime | None
class SourceIdentityResponse(HttpModel): source: str; official_id: str
class InitialEvidenceResponse(HttpModel): category: str; configured_term: str; matched_text: str; field: str
class InitialScreeningResponse(HttpModel):
    evaluation_id: UUID; state: str; reason: str; engine_version: str; evaluated_at: datetime; evidence: list[InitialEvidenceResponse]
class DocumentCoverageResponse(HttpModel):
    documents: int; sources: int; pages: int; pages_with_text: int; likely_scanned_sources: int; failed_sources: int; unsupported_sources: int; complete: bool
class DocumentScreeningResponse(HttpModel):
    evaluation_id: UUID; state: str; reason: str; engine_version: str; fingerprint: str; evaluated_at: datetime; coverage: DocumentCoverageResponse
class OperationalResolutionResponse(HttpModel):
    resolution_id: UUID; initial_evaluation_id: UUID; document_evaluation_id: UUID | None; state: str; reason: str; rule: str; fingerprint: str; resolved_at: datetime; state_diverged: bool | None; reason_diverged: bool | None; divergence_kind: str | None
class HumanReviewResponse(HttpModel):
    review_id: UUID; operational_resolution_id: UUID; decision: HumanReviewDecision; reason: str; reviewer_id: str; reviewer_display_name: str | None; comment: str | None; decided_at: datetime; was_stale_at_decision: bool
class ReviewCreateRequest(HttpModel):
    operational_resolution_id: UUID
    decision: HumanReviewDecision
    reason: HumanReviewReason
    comment: str | None = Field(default=None, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    allow_stale: bool = False
class ReviewCreatedResponse(HttpModel):
    review_id: UUID
    process_id: UUID
    profile_id: UUID
    operational_resolution_id: UUID
    decision: HumanReviewDecision
    reason: HumanReviewReason
    comment: str | None
    reviewer_id: str
    reviewer_display_name: str | None
    was_stale_at_decision: bool
    latest_resolution_id_at_decision: UUID
    decided_at: datetime
class LatestObservationResponse(HttpModel):
    observation_id: UUID; round_id: UUID; source: str; captured_at: datetime | None; persisted_at: datetime
class OpportunityCountersResponse(HttpModel): documents: int; artifacts: int; extracted_sources: int; pages: int; pages_with_text: int
class OpportunityDetailResponse(HttpModel):
    opportunity: OpportunityListItemResponse; description: str | None; source_identities: list[SourceIdentityResponse]; latest_observation: LatestObservationResponse | None; initial_screening: InitialScreeningResponse | None; document_screening: DocumentScreeningResponse | None; operational_resolution: OperationalResolutionResponse | None; current_human_review: HumanReviewResponse | None; latest_historical_review: HumanReviewResponse | None; counters: OpportunityCountersResponse

class ExtractionMetadataResponse(HttpModel):
    extraction_id: UUID; source_id: UUID; extractor_name: str; extractor_version: str; status: str; pages: int; pages_with_text: int; likely_scanned: bool; started_at: datetime; finished_at: datetime
class DocumentMemberResponse(HttpModel):
    path: str; sha256: str | None; detected_type: str | None; safe: bool; extracted: bool; pages: int | None; text_status: str | None
class OpportunityDocumentResponse(HttpModel):
    document_id: UUID; official_document_id: str; title: str | None; document_type: str | None; source: str; source_url: str | None; first_seen_at: datetime; last_seen_at: datetime; has_artifact: bool; artifact_sha256: str | None; detected_type: str | None; acquisition_status: str | None; acquired_at: datetime | None; text_status: str | None; extracted_pages: int | None; likely_scanned: bool | None; extractions: list[ExtractionMetadataResponse]; members: list[DocumentMemberResponse]
class DocumentEvidenceResponse(HttpModel):
    category: str; configured_term: str; matched_text: str; context_snippet: str; page_number: int; source_path: str; source_sha256: str; document_id: UUID | None; negated: bool
class TimelineItemResponse(HttpModel):
    event_type: str; occurred_at: datetime; title: str; summary: str; reference_id: UUID; metadata: list[list[str]]

class ReviewerResponse(HttpModel): reviewer_id: str; display_name: str | None
class ReviewQueueItemResponse(HttpModel):
    process_id: UUID; profile_id: UUID; operational_resolution_id: UUID; operational_state: str; operational_reason: str; resolution_resolved_at: datetime; human_review_status: HumanReviewStatus; human_decision: HumanReviewDecision | None; human_reason: str | None; reviewer: ReviewerResponse | None; reviewed_at: datetime | None
class DashboardReviewQueueItemResponse(HttpModel): opportunity: OpportunityListItemResponse; review: ReviewQueueItemResponse
class ModalityOutcomeResponse(HttpModel):
    modality_code: int; complete: bool; pages_processed: int; records_received: int; processes_mapped: int; failed_page: int | None; failure_reason: str | None; mapping_errors_count: int
class CollectionRoundListItemResponse(HttpModel):
    round_id: UUID; source: str; started_at: datetime; finished_at: datetime | None; status: str; pages_expected: int; pages_processed: int; page_errors: int; records_collected: int; unique_processes: int; modalities_attempted: list[int]; modality_outcomes: list[ModalityOutcomeResponse]
class CollectionRoundDetailResponse(HttpModel):
    round: CollectionRoundListItemResponse; errors: int; candidates: int; selected: int; pending: int; discarded: int; documents_found: int
