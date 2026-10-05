"""Atalhos para montar inputs da resolução."""

from dataclasses import replace
from uuid import UUID, uuid4

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import (
    DocumentCoverage,
    DocumentScreeningEvaluation,
)
from collector.application.resolution.resolver import OperationalResolver
from collector.application.screening.results import ScreeningEvaluation
from collector.domain import ScreeningStatus
from tests.application.document_screening.helpers import screen_pages
from tests.application.screening.helpers import screen


def align(initial: ScreeningEvaluation, document: DocumentScreeningEvaluation | None):
    process_id = initial.process_id
    if document is None:
        return initial, None
    return initial, replace(document, process_id=process_id, profile_id=initial.profile_id)


def resolve(initial: ScreeningEvaluation, document: DocumentScreeningEvaluation | None = None):
    initial, document = align(initial, document)
    return OperationalResolver().resolve(initial, document)


def with_coverage(
    evaluation: DocumentScreeningEvaluation, *, complete: bool
) -> DocumentScreeningEvaluation:
    coverage = replace(
        evaluation.coverage,
        complete=complete,
        likely_scanned_sources=0 if complete else max(1, evaluation.coverage.likely_scanned_sources),
    )
    return replace(evaluation, coverage=coverage)


def document_case(
    text: str,
    *,
    complete: bool = True,
    process_id: UUID | None = None,
    fingerprint: str | None = None,
) -> DocumentScreeningEvaluation:
    evaluation = screen_pages(text)
    if process_id is not None:
        evaluation = replace(evaluation, process_id=process_id)
    if fingerprint is not None:
        evaluation = replace(evaluation, document_set_fingerprint=fingerprint)
    return with_coverage(evaluation, complete=complete)


def known_3341_initial() -> ScreeningEvaluation:
    """Fixture explícita da avaliação histórica conhecida. Não veio do banco."""

    return replace(
        screen(
            "Manutenção preventiva e fornecimento de aparelhos de ar condicionado."
        ),
        # O texto acima reproduz o reason MIXED_MAINTENANCE_SUPPLY da triagem
        # inicial histórica informada para 00509968000148/2026/3341/1.
    )


def known_3341_document(process_id: UUID) -> DocumentScreeningEvaluation:
    """Replica o resultado documental observado no Commit 13 (não relê o banco)."""

    evaluation = screen_pages("Regras para apresentação da proposta.")
    return replace(
        evaluation,
        process_id=process_id,
        document_set_fingerprint="3b8c030795802672f129dfee1cc4a690c76cbee8730c4f0624d7038366640ed3",
        state=ScreeningStatus.PENDING,
        reason_code=DocumentReasonCode.DOCUMENT_NO_DECISIVE_EVIDENCE,
        coverage=DocumentCoverage(
            documents_considered=1,
            sources_considered=2,
            pages_considered=55,
            pages_with_text=55,
            likely_scanned_sources=0,
            failed_sources=0,
            unsupported_sources=0,
            complete=True,
        ),
    )
