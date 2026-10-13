"""UI-oriented, immutable projections. Decimal and aware timestamps stay native."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from collector.application.human_review.models import HumanReviewDecision, HumanReviewStatus, ReviewQueueItem
from .filters import TimeRange


def description_preview(description: str | None) -> str | None:
    return description[:300] if description is not None else None


@dataclass(frozen=True)
class SourceIdentityItem:
    source: str
    official_id: str


@dataclass(frozen=True)
class OpportunityListItem:
    process_id: UUID
    source: str | None
    official_id: str | None
    description_preview: str | None
    organization_name: str | None
    organization_cnpj: str | None
    municipality_name: str | None
    uf: str | None
    modality: str | None
    estimated_value: Decimal | None
    publication_at: datetime | None
    proposal_deadline_at: datetime | None
    official_url: str | None
    notice_number: str | None
    operational_resolution_id: UUID | None
    operational_state: str | None
    operational_reason: str | None
    operational_resolved_at: datetime | None
    human_review_status: HumanReviewStatus
    human_decision: HumanReviewDecision | None
    human_reason: str | None
    reviewed_at: datetime | None
    documents_count: int
    has_text: bool
    has_document_screening: bool
    latest_capture_at: datetime | None
    rhs_id: str | None = None
    monthly_value: Decimal | None = None


@dataclass(frozen=True)
class DashboardReviewQueueItem:
    opportunity: OpportunityListItem
    review: ReviewQueueItem


@dataclass(frozen=True)
class InitialEvidenceItem:
    category: str
    configured_term: str
    matched_text: str
    field: str


@dataclass(frozen=True)
class DocumentEvidenceItem:
    category: str
    configured_term: str
    matched_text: str
    context_snippet: str
    page_number: int
    source_path: str
    source_sha256: str
    document_id: UUID | None
    negated: bool


@dataclass(frozen=True)
class InitialScreeningItem:
    evaluation_id: UUID
    state: str
    reason: str
    engine_version: str
    evaluated_at: datetime
    evidence: tuple[InitialEvidenceItem, ...]


@dataclass(frozen=True)
class DocumentCoverage:
    documents: int
    sources: int
    pages: int
    pages_with_text: int
    likely_scanned_sources: int
    failed_sources: int
    unsupported_sources: int
    complete: bool


@dataclass(frozen=True)
class DocumentScreeningItem:
    evaluation_id: UUID
    state: str
    reason: str
    engine_version: str
    fingerprint: str
    evaluated_at: datetime
    coverage: DocumentCoverage


@dataclass(frozen=True)
class OperationalResolutionItem:
    resolution_id: UUID
    initial_evaluation_id: UUID
    document_evaluation_id: UUID | None
    state: str
    reason: str
    rule: str
    fingerprint: str
    resolved_at: datetime
    state_diverged: bool | None
    reason_diverged: bool | None
    divergence_kind: str | None


@dataclass(frozen=True)
class HumanReviewItem:
    review_id: UUID
    operational_resolution_id: UUID
    decision: HumanReviewDecision
    reason: str
    reviewer_id: str
    reviewer_display_name: str | None
    comment: str | None
    decided_at: datetime
    was_stale_at_decision: bool


@dataclass(frozen=True)
class LatestObservation:
    observation_id: UUID
    round_id: UUID
    source: str
    captured_at: datetime | None
    persisted_at: datetime


@dataclass(frozen=True)
class OpportunityCounters:
    documents: int
    artifacts: int
    extracted_sources: int
    pages: int
    pages_with_text: int


@dataclass(frozen=True)
class OpportunityDetail:
    opportunity: OpportunityListItem
    description: str | None
    source_identities: tuple[SourceIdentityItem, ...]
    latest_observation: LatestObservation | None
    initial_screening: InitialScreeningItem | None
    document_screening: DocumentScreeningItem | None
    operational_resolution: OperationalResolutionItem | None
    current_human_review: HumanReviewItem | None
    latest_historical_review: HumanReviewItem | None
    counters: OpportunityCounters


@dataclass(frozen=True)
class ExtractionMetadata:
    extraction_id: UUID
    source_id: UUID
    extractor_name: str
    extractor_version: str
    status: str
    pages: int
    pages_with_text: int
    likely_scanned: bool
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True)
class DocumentMemberItem:
    path: str
    sha256: str | None
    detected_type: str | None
    safe: bool
    extracted: bool
    pages: int | None
    text_status: str | None


@dataclass(frozen=True)
class OpportunityDocumentItem:
    document_id: UUID
    official_document_id: str
    title: str | None
    document_type: str | None
    source: str
    source_url: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    has_artifact: bool
    artifact_sha256: str | None
    detected_type: str | None
    acquisition_status: str | None
    acquired_at: datetime | None
    text_status: str | None
    extracted_pages: int | None
    likely_scanned: bool | None
    extractions: tuple[ExtractionMetadata, ...]
    members: tuple[DocumentMemberItem, ...]


@dataclass(frozen=True)
class OpportunityTimelineItem:
    event_type: str
    occurred_at: datetime
    title: str
    summary: str
    reference_id: UUID
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ModalityOutcomeItem:
    modality_code: int
    complete: bool
    pages_processed: int
    records_received: int
    processes_mapped: int
    failed_page: int | None
    failure_reason: str | None
    mapping_errors_count: int


@dataclass(frozen=True)
class CollectionRoundListItem:
    round_id: UUID
    source: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    pages_expected: int
    pages_processed: int
    page_errors: int
    records_collected: int
    unique_processes: int
    modalities_attempted: tuple[int, ...]
    modality_outcomes: tuple[ModalityOutcomeItem, ...]


@dataclass(frozen=True)
class CollectionRoundDetail:
    round: CollectionRoundListItem
    errors: int
    candidates: int
    selected: int
    pending: int
    discarded: int
    documents_found: int


@dataclass(frozen=True)
class SourceCoverageSummary:
    source: str
    rounds: int
    successful_rounds: int
    partial_rounds: int
    failed_rounds: int
    records_collected: int
    unique_processes: int


@dataclass(frozen=True)
class CurrentSnapshot:
    processes_total: int
    current_candidate: int
    current_pending: int
    current_discarded: int
    needs_review: int
    selected: int
    human_pending: int
    human_discarded: int
    stale_reviews: int
    documents_total: int
    documents_with_artifact: int
    documents_with_text: int


@dataclass(frozen=True)
class PeriodActivity:
    records_collected: int
    processes_first_seen: int
    documents_discovered: int
    document_screenings_total: int
    operational_resolutions_total: int
    human_reviews_total: int
    rounds_total: int
    rounds_success: int
    rounds_partial: int
    rounds_failed: int


@dataclass(frozen=True)
class PilotFunnel:
    records_collected: int
    unique_processes: int
    initial_candidate: int
    initial_pending: int
    initial_discarded: int
    document_evaluated: int
    operational_candidate: int
    operational_pending: int
    operational_discarded: int
    selected: int
    human_pending: int
    human_discarded: int


@dataclass(frozen=True)
class DashboardSummary:
    profile_id: UUID
    period: TimeRange
    current_snapshot: CurrentSnapshot
    period_activity: PeriodActivity
    funnel: PilotFunnel
    source_coverage: tuple[SourceCoverageSummary, ...]
