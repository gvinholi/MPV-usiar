"""Compara triagem inicial e documental. Sem estado operacional."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from enum import Enum

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.screening.reasons import ReasonCode
from collector.application.screening.results import ScreeningEvaluation
from collector.domain import ScreeningStatus


class DivergenceKind(Enum):
    NONE = "NONE"
    STATE_ONLY = "STATE_ONLY"
    REASON_ONLY = "REASON_ONLY"
    STATE_AND_REASON = "STATE_AND_REASON"


@dataclass(frozen=True)
class ScreeningComparison:
    process_id: UUID
    initial_state: ScreeningStatus | None
    initial_reason: ReasonCode | None
    document_state: ScreeningStatus | None
    document_reason: DocumentReasonCode | None
    state_diverged: bool
    reason_diverged: bool
    divergence_kind: DivergenceKind

    @property
    def diverged(self) -> bool:
        """Compatível com o Commit 13: divergência de estado."""

        return self.state_diverged


def compare_screenings(
    initial: ScreeningEvaluation | None,
    document: DocumentScreeningEvaluation | None,
) -> ScreeningComparison:
    process_id = (
        document.process_id
        if document is not None
        else initial.process_id if initial is not None else None
    )
    if process_id is None:
        raise ValueError("comparação exige ao menos uma avaliação")
    have_both = initial is not None and document is not None
    state_diverged = have_both and initial.state is not document.state
    reason_diverged = have_both and initial.reason_code.value != document.reason_code.value
    if state_diverged and reason_diverged:
        kind = DivergenceKind.STATE_AND_REASON
    elif state_diverged:
        kind = DivergenceKind.STATE_ONLY
    elif reason_diverged:
        kind = DivergenceKind.REASON_ONLY
    else:
        kind = DivergenceKind.NONE
    return ScreeningComparison(
        process_id=process_id,
        initial_state=None if initial is None else initial.state,
        initial_reason=None if initial is None else initial.reason_code,
        document_state=None if document is None else document.state,
        document_reason=None if document is None else document.reason_code,
        state_diverged=state_diverged,
        reason_diverged=reason_diverged,
        divergence_kind=kind,
    )
