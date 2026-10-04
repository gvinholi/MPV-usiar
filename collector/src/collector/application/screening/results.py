"""Resultado auditável de uma avaliação de perfil."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.screening.reasons import ReasonCode
from collector.domain import ScreeningStatus


ENGINE_VERSION = "1"

ALLOWED_STATES = frozenset(
    {
        ScreeningStatus.CANDIDATE,
        ScreeningStatus.PENDING,
        ScreeningStatus.DISCARDED,
    }
)


@dataclass(frozen=True)
class ScreeningEvidence:
    category: str
    configured_term: str
    field: str
    matched_text: str


@dataclass(frozen=True)
class ScreeningEvaluation:
    id: UUID
    process_id: UUID
    observation_id: UUID
    profile_code: str
    profile_version: str
    state: ScreeningStatus
    reason_code: ReasonCode
    reason_text: str
    evaluated_at: datetime
    engine_version: str
    field: str
    evidence: tuple[ScreeningEvidence, ...]
    profile_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.state not in ALLOWED_STATES:
            raise ValueError("triagem automática não atribui SELECTED nem CONFIRMED")
        if self.state is ScreeningStatus.SELECTED or self.state is ScreeningStatus.CONFIRMED:
            raise ValueError("triagem automática não atribui SELECTED nem CONFIRMED")


@dataclass(frozen=True)
class ScreeningSummary:
    evaluated: int
    candidates: int
    pending: int
    discarded: int
    by_reason: dict[str, int]


def summarize(evaluations: tuple[ScreeningEvaluation, ...] | list[ScreeningEvaluation]) -> ScreeningSummary:
    by_reason: dict[str, int] = {}
    candidates = pending = discarded = 0
    for evaluation in evaluations:
        by_reason[evaluation.reason_code.value] = (
            by_reason.get(evaluation.reason_code.value, 0) + 1
        )
        if evaluation.state is ScreeningStatus.CANDIDATE:
            candidates += 1
        elif evaluation.state is ScreeningStatus.PENDING:
            pending += 1
        elif evaluation.state is ScreeningStatus.DISCARDED:
            discarded += 1
    return ScreeningSummary(
        evaluated=len(evaluations),
        candidates=candidates,
        pending=pending,
        discarded=discarded,
        by_reason=by_reason,
    )
