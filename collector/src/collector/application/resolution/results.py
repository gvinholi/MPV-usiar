"""Resultado auditável da resolução operacional."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.document_screening.compare import DivergenceKind
from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.domain import ScreeningStatus

ALLOWED_STATES = frozenset(
    {
        ScreeningStatus.CANDIDATE,
        ScreeningStatus.PENDING,
        ScreeningStatus.DISCARDED,
    }
)


@dataclass(frozen=True)
class OperationalResolution:
    id: UUID
    process_id: UUID
    profile_code: str
    profile_version: str
    initial_evaluation_id: UUID
    document_evaluation_id: UUID | None
    resolver_engine_version: str
    resolution_fingerprint: str
    state: ScreeningStatus
    reason_code: OperationalReasonCode
    reason_text: str
    rule_code: OperationalRuleCode
    coverage_complete: bool
    state_diverged: bool | None
    reason_diverged: bool | None
    divergence_kind: DivergenceKind | None
    resolved_at: datetime
    initial_state: ScreeningStatus
    document_state: ScreeningStatus | None = None
    profile_id: UUID | None = None
    document_set_fingerprint: str | None = None
    initial_input_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.state not in ALLOWED_STATES:
            raise ValueError("resolução operacional não atribui SELECTED nem CONFIRMED")
        if self.state is ScreeningStatus.SELECTED or self.state is ScreeningStatus.CONFIRMED:
            raise ValueError("resolução operacional não atribui SELECTED nem CONFIRMED")


@dataclass(frozen=True)
class OperationalSummary:
    resolutions_total: int
    candidate: int
    pending: int
    discarded: int
    initial_only: int
    document_based: int
    incomplete_document: int
    state_divergences: int
    reason_divergences: int
    recovered_from_initial_discard: int
    candidate_downgraded_to_discarded: int
    changed_state: int
    unchanged_state: int
