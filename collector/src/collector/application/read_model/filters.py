"""Validated read requests; no SQL or transport types."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from collector.application.human_review.models import HumanReviewDecision, HumanReviewStatus, ReviewQueue


@dataclass(frozen=True)
class TimeRange:
    from_datetime: datetime | None = None
    to_datetime: datetime | None = None

    def __post_init__(self):
        for value in (self.from_datetime, self.to_datetime):
            if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
                raise ValueError("timestamps must be timezone-aware")
        if self.from_datetime and self.to_datetime and self.from_datetime >= self.to_datetime:
            raise ValueError("expected from_datetime < to_datetime")


@dataclass(frozen=True)
class ProfileScope:
    profile_id: UUID | None = None
    profile_code: str | None = None

    def __post_init__(self):
        if (self.profile_id is None) == (self.profile_code is None):
            raise ValueError("provide exactly one profile_id or profile_code")
        if self.profile_id is not None and not isinstance(self.profile_id, UUID):
            raise ValueError("invalid profile_id")
        if self.profile_code is not None and (not isinstance(self.profile_code, str) or not self.profile_code.strip()):
            raise ValueError("invalid profile_code")


class SortField(StrEnum):
    PUBLICATION_AT = "publication_at"
    PROPOSAL_DEADLINE_AT = "proposal_deadline_at"
    ESTIMATED_VALUE = "estimated_value"
    LATEST_CAPTURE_AT = "latest_capture_at"
    OPERATIONAL_RESOLVED_AT = "operational_resolved_at"
    REVIEWED_AT = "reviewed_at"


class SortDirection(StrEnum):
    ASC = "ASC"
    DESC = "DESC"


@dataclass(frozen=True)
class OpportunitySort:
    field: SortField = SortField.LATEST_CAPTURE_AT
    direction: SortDirection = SortDirection.DESC

    def __post_init__(self):
        object.__setattr__(self, "field", SortField(self.field))
        object.__setattr__(self, "direction", SortDirection(self.direction))


@dataclass(frozen=True)
class OpportunityFilters:
    operational_state: str | tuple[str, ...] | None = None
    human_review_status: HumanReviewStatus | None = None
    human_decision: HumanReviewDecision | None = None
    source: str | None = None
    uf: str | None = None
    municipality: str | None = None
    modality: str | None = None
    publication: TimeRange = field(default_factory=TimeRange)
    proposal_deadline: TimeRange = field(default_factory=TimeRange)
    captured: TimeRange = field(default_factory=TimeRange)
    has_documents: bool | None = None
    has_text: bool | None = None
    has_document_screening: bool | None = None
    search: str | None = None
    review_queue: ReviewQueue | None = None
    include_operational_discarded: bool = False

    def __post_init__(self):
        allowed_states = ("CANDIDATE", "PENDING", "DISCARDED")
        if isinstance(self.operational_state, tuple):
            if not self.operational_state or any(
                state not in allowed_states for state in self.operational_state
            ):
                raise ValueError("invalid operational state")
            object.__setattr__(
                self,
                "operational_state",
                tuple(dict.fromkeys(self.operational_state)),
            )
        elif self.operational_state not in (None, *allowed_states):
            raise ValueError("invalid operational state")
        for name, enum in (("human_review_status", HumanReviewStatus), ("human_decision", HumanReviewDecision), ("review_queue", ReviewQueue)):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, enum(getattr(self, name)))
        for name in ("publication", "proposal_deadline", "captured"):
            if not isinstance(getattr(self, name), TimeRange):
                raise ValueError("expected TimeRange")
        for name in ("has_documents", "has_text", "has_document_screening"):
            if getattr(self, name) is not None and type(getattr(self, name)) is not bool:
                raise ValueError("expected boolean filter")
        if type(self.include_operational_discarded) is not bool:
            raise ValueError("expected boolean include_operational_discarded")
        for name in ("source", "uf", "municipality", "modality", "search"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 300):
                raise ValueError(f"invalid {name}")
        if self.source not in (None, "PNCP", "RHS"):
            raise ValueError("unknown source")
        if self.uf is not None:
            if len(self.uf) != 2 or not self.uf.isalpha():
                raise ValueError("invalid UF")
            object.__setattr__(self, "uf", self.uf.upper())
