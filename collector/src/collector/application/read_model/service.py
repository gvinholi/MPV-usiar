"""Application entry point for future transports, without write-side dependencies."""
from collector.application.human_review.models import ReviewQueue
from uuid import UUID
from .filters import OpportunityFilters, OpportunitySort, ProfileScope, TimeRange
from .models import (
    CollectionRoundDetail, CollectionRoundListItem, DashboardReviewQueueItem, DashboardSummary,
    DocumentEvidenceItem, OpportunityDetail, OpportunityDocumentItem, OpportunityListItem,
    OpportunityTimelineItem, PilotFunnel, SourceCoverageSummary,
)
from .pagination import Page, Pagination
from .ports import ReadModelQueries


class DashboardQueries:
    def __init__(self, queries: ReadModelQueries):
        self._queries = queries

    def dashboard_summary(self, scope: ProfileScope, period: TimeRange = TimeRange()) -> DashboardSummary:
        return self._queries.dashboard_summary(scope, period)

    def pilot_funnel(self, scope: ProfileScope, period: TimeRange = TimeRange()) -> PilotFunnel:
        return self._queries.pilot_funnel(scope, period)

    def list_opportunities(self, scope: ProfileScope, filters: OpportunityFilters = OpportunityFilters(),
                           pagination: Pagination = Pagination(), sort: OpportunitySort = OpportunitySort()) -> Page[OpportunityListItem]:
        return self._queries.list_opportunities(scope, filters, pagination, sort)

    def get_opportunity(self, process_id: UUID, scope: ProfileScope) -> OpportunityDetail:
        return self._queries.get_opportunity(process_id, scope)

    def get_opportunity_by_source_identity(self, source: str, official_id: str, scope: ProfileScope) -> OpportunityDetail:
        if not isinstance(official_id, str) or not official_id.strip():
            raise ValueError('official_id is required')
        OpportunityFilters(source=source)
        return self._queries.get_opportunity_by_source_identity(source, official_id, scope)

    def documents(self, process_id: UUID, pagination: Pagination = Pagination()) -> Page[OpportunityDocumentItem]:
        return self._queries.documents(process_id, pagination)

    def document_evidence(self, process_id: UUID, scope: ProfileScope, pagination: Pagination = Pagination()) -> Page[DocumentEvidenceItem]:
        return self._queries.document_evidence(process_id, scope, pagination)

    def timeline(self, process_id: UUID, scope: ProfileScope, pagination: Pagination = Pagination()) -> Page[OpportunityTimelineItem]:
        return self._queries.timeline(process_id, scope, pagination)

    def collection_rounds(self, period: TimeRange = TimeRange(), pagination: Pagination = Pagination(), source: str | None = None) -> Page[CollectionRoundListItem]:
        OpportunityFilters(source=source)
        return self._queries.collection_rounds(period, pagination, source)

    def collection_round_detail(self, round_id: UUID) -> CollectionRoundDetail:
        return self._queries.collection_round_detail(round_id)

    def source_coverage(self, period: TimeRange = TimeRange()) -> tuple[SourceCoverageSummary, ...]:
        return self._queries.source_coverage(period)

    def review_queue(self, scope: ProfileScope, queue: ReviewQueue = ReviewQueue.NEEDS_REVIEW,
                     filters: OpportunityFilters = OpportunityFilters(), pagination: Pagination = Pagination(),
                     sort: OpportunitySort = OpportunitySort()) -> Page[DashboardReviewQueueItem]:
        return self._queries.review_queue(scope, ReviewQueue(queue), filters, pagination, sort)
