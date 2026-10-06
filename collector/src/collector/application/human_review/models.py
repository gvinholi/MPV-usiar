"""Immutable human decisions and pure policies, independent of persistence."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class HumanReviewDecision(StrEnum):
    SELECTED = "SELECTED"
    DISCARDED = "DISCARDED"
    PENDING = "PENDING"


class HumanReviewReason(StrEnum):
    RELEVANT_SCOPE_CONFIRMED = "RELEVANT_SCOPE_CONFIRMED"
    COMMERCIAL_INTEREST = "COMMERCIAL_INTEREST"
    TECHNICAL_FIT = "TECHNICAL_FIT"
    REVIEWED_AND_APPROVED = "REVIEWED_AND_APPROVED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    ISOLATED_INSTALLATION = "ISOLATED_INSTALLATION"
    EQUIPMENT_PURCHASE_ONLY = "EQUIPMENT_PURCHASE_ONLY"
    PARTS_SUPPLY_ONLY = "PARTS_SUPPLY_ONLY"
    DEADLINE_NOT_VIABLE = "DEADLINE_NOT_VIABLE"
    TECHNICAL_REQUIREMENT_NOT_VIABLE = "TECHNICAL_REQUIREMENT_NOT_VIABLE"
    COMMERCIAL_DECISION = "COMMERCIAL_DECISION"
    DUPLICATE_OPPORTUNITY = "DUPLICATE_OPPORTUNITY"
    OTHER = "OTHER"
    NEEDS_TECHNICAL_REVIEW = "NEEDS_TECHNICAL_REVIEW"
    NEEDS_COMMERCIAL_REVIEW = "NEEDS_COMMERCIAL_REVIEW"
    NEEDS_DOCUMENT_REVIEW = "NEEDS_DOCUMENT_REVIEW"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


ALLOWED_REASONS = {
    HumanReviewDecision.SELECTED: frozenset(HumanReviewReason(x) for x in (
        "RELEVANT_SCOPE_CONFIRMED", "COMMERCIAL_INTEREST", "TECHNICAL_FIT", "REVIEWED_AND_APPROVED")),
    HumanReviewDecision.DISCARDED: frozenset(HumanReviewReason(x) for x in (
        "OUT_OF_SCOPE", "ISOLATED_INSTALLATION", "EQUIPMENT_PURCHASE_ONLY", "PARTS_SUPPLY_ONLY",
        "DEADLINE_NOT_VIABLE", "TECHNICAL_REQUIREMENT_NOT_VIABLE", "COMMERCIAL_DECISION",
        "DUPLICATE_OPPORTUNITY", "OTHER")),
    HumanReviewDecision.PENDING: frozenset(HumanReviewReason(x) for x in (
        "NEEDS_TECHNICAL_REVIEW", "NEEDS_COMMERCIAL_REVIEW", "NEEDS_DOCUMENT_REVIEW",
        "INSUFFICIENT_INFORMATION", "OTHER")),
}
COMMENT_LIMIT = 4000


@dataclass(frozen=True)
class ReviewerIdentity:
    reviewer_id: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer_id, str) or not self.reviewer_id.strip() or len(self.reviewer_id) > 200:
            raise ValueError("reviewer_id requires 1..200 nonblank characters")
        if self.display_name is not None and (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > 200
        ):
            raise ValueError("invalid display_name")


@dataclass(frozen=True)
class RecordHumanReviewCommand:
    operational_resolution_id: UUID
    reviewer: ReviewerIdentity
    decision: HumanReviewDecision
    reason: HumanReviewReason
    idempotency_key: str
    comment: str | None = None
    allow_stale: bool = False

    def __post_init__(self) -> None:
        validate_command(self)


def validate_command(command: RecordHumanReviewCommand) -> None:
    if not isinstance(command.operational_resolution_id, UUID):
        raise ValueError("resolution id must be UUID")
    if not isinstance(command.reviewer, ReviewerIdentity):
        raise ValueError("reviewer required")
    if not isinstance(command.decision, HumanReviewDecision) or not isinstance(command.reason, HumanReviewReason):
        raise ValueError("explicit human decision and reason required")
    if command.reason not in ALLOWED_REASONS[command.decision]:
        raise ValueError("reason incompatible with decision")
    if not isinstance(command.idempotency_key, str) or not command.idempotency_key.strip() or len(command.idempotency_key) > 200:
        raise ValueError("idempotency_key requires 1..200 nonblank characters")
    if command.comment is not None and (not isinstance(command.comment, str) or len(command.comment) > COMMENT_LIMIT):
        raise ValueError("comment exceeds 4000 characters")
    if command.reason is HumanReviewReason.OTHER and not (command.comment and command.comment.strip()):
        raise ValueError("OTHER requires comment")
    if type(command.allow_stale) is not bool:
        raise ValueError("allow_stale must be boolean")


class HumanReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    REVIEWED = "REVIEWED"
    STALE = "STALE"


class ReviewQueue(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SELECTED = "SELECTED"
    HUMAN_DISCARDED = "HUMAN_DISCARDED"
    HUMAN_PENDING = "HUMAN_PENDING"
    STALE_REVIEW = "STALE_REVIEW"


@dataclass(frozen=True)
class HumanReview:
    id: UUID
    process_id: UUID
    profile_id: UUID
    command: RecordHumanReviewCommand
    was_stale_at_decision: bool
    latest_resolution_id_at_decision: UUID
    resolution_fingerprint: str
    operational_state_snapshot: str
    decided_at: datetime
    created_at: datetime
    sequence: int

    @property
    def operational_resolution_id(self) -> UUID:
        return self.command.operational_resolution_id

    @property
    def reviewer(self) -> ReviewerIdentity:
        return self.command.reviewer

    @property
    def decision(self) -> HumanReviewDecision:
        return self.command.decision

    @property
    def reason_code(self) -> HumanReviewReason:
        return self.command.reason

    @property
    def comment(self) -> str | None:
        return self.command.comment

    @property
    def idempotency_key(self) -> str:
        return self.command.idempotency_key


def derive_status(has_current_review: bool, has_history: bool) -> HumanReviewStatus:
    if has_current_review:
        return HumanReviewStatus.REVIEWED
    return HumanReviewStatus.STALE if has_history else HumanReviewStatus.UNREVIEWED


@dataclass(frozen=True)
class ReviewQueueItem:
    process_id: UUID
    profile_id: UUID
    operational_resolution_id: UUID
    operational_state: str
    operational_reason: str
    resolution_resolved_at: datetime
    human_review_status: HumanReviewStatus
    human_decision: HumanReviewDecision | None
    human_reason: HumanReviewReason | None
    reviewer: ReviewerIdentity | None
    reviewed_at: datetime | None


@dataclass(frozen=True)
class HumanReviewSummary:
    current_resolutions: int
    needs_review: int
    reviewed: int
    stale_reviews: int
    selected: int
    human_discarded: int
    human_pending: int
    reviews_total: int
    stale_overrides_total: int


class StaleOperationalResolutionError(ValueError):
    def __init__(self, reviewed_resolution_id: UUID, latest_resolution_id: UUID):
        self.reviewed_resolution_id = reviewed_resolution_id
        self.latest_resolution_id = latest_resolution_id
        super().__init__(f"reviewed resolution {reviewed_resolution_id}; current resolution {latest_resolution_id}")


class IdempotencyConflictError(ValueError):
    pass


def check_stale(command: RecordHumanReviewCommand, latest_id: UUID) -> bool:
    stale = command.operational_resolution_id != latest_id
    if stale and not command.allow_stale:
        raise StaleOperationalResolutionError(command.operational_resolution_id, latest_id)
    return stale


def in_queue(item: ReviewQueueItem, queue: ReviewQueue | None, include_discarded: bool) -> bool:
    if queue is None:
        return include_discarded or item.operational_state != "DISCARDED" or item.human_decision is not None
    if queue == ReviewQueue.NEEDS_REVIEW:
        return item.human_review_status != HumanReviewStatus.REVIEWED and (include_discarded or item.operational_state != "DISCARDED")
    if queue == ReviewQueue.STALE_REVIEW:
        return item.human_review_status == HumanReviewStatus.STALE
    decisions = {
        ReviewQueue.SELECTED: HumanReviewDecision.SELECTED,
        ReviewQueue.HUMAN_DISCARDED: HumanReviewDecision.DISCARDED,
        ReviewQueue.HUMAN_PENDING: HumanReviewDecision.PENDING,
    }
    return item.human_decision == decisions[ReviewQueue(queue)]
