"""Compara triagem inicial e documental. Sem estado final combinado."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.screening.reasons import ReasonCode
from collector.application.screening.results import ScreeningEvaluation
from collector.domain import ScreeningStatus


@dataclass(frozen=True)
class ScreeningComparison:
    process_id: UUID
    initial_state: ScreeningStatus | None
    initial_reason: ReasonCode | None
    document_state: ScreeningStatus | None
    document_reason: DocumentReasonCode | None
    diverged: bool


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
    diverged = (
        initial is not None
        and document is not None
        and initial.state is not document.state
    )
    return ScreeningComparison(
        process_id=process_id,
        initial_state=None if initial is None else initial.state,
        initial_reason=None if initial is None else initial.reason_code,
        document_state=None if document is None else document.state,
        document_reason=None if document is None else document.reason_code,
        diverged=diverged,
    )
