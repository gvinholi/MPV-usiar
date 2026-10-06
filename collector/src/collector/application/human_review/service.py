"""Atomic persistence port: stale check and insert share one transaction."""
from datetime import UTC, datetime
from typing import Callable, Protocol
from uuid import UUID
from .models import (
    HumanReview, HumanReviewSummary, RecordHumanReviewCommand, ReviewQueue,
    ReviewQueueItem, validate_command,
)


class HumanReviewRepository(Protocol):
    def record(self, command: RecordHumanReviewCommand, *, clock: Callable[[], datetime]) -> HumanReview: ...


class HumanReviewQueries(Protocol):
    def latest_review_for_resolution(self, resolution_id: UUID) -> HumanReview | None: ...
    def list_reviews_for_process(self, process_id: UUID, profile_id: UUID) -> tuple[HumanReview, ...]: ...
    def review_status_for_process(self, process_id: UUID, profile_id: UUID) -> ReviewQueueItem | None: ...
    def list_queue(self, queue: ReviewQueue | None = None, *, profile_id: UUID | None = None,
                   include_operational_discarded: bool = False) -> tuple[ReviewQueueItem, ...]: ...
    def summary(self, *, profile_id: UUID | None = None) -> HumanReviewSummary: ...


class RecordHumanReview:
    def __init__(self, repository: HumanReviewRepository, *, clock: Callable[[], datetime] | None = None):
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))

    def execute(self, command: RecordHumanReviewCommand) -> HumanReview:
        validate_command(command)
        return self.repository.record(command, clock=self.clock)
