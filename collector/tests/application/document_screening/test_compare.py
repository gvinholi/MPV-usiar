"""Comparação inicial × documental. Sem estado final."""

from dataclasses import replace
from uuid import uuid4

from collector.application.document_screening.compare import compare_screenings
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.domain import ScreeningStatus
from tests.application.document_screening.helpers import screen_pages
from tests.application.screening.helpers import screen


def test_divergence_pending_to_candidate() -> None:
    process_id = uuid4()
    initial = replace(
        screen("Manutenção e fornecimento de aparelhos de ar condicionado."),
        process_id=process_id,
    )
    document = replace(
        screen_pages(
            "Contratação de manutenção preventiva dos aparelhos de ar condicionado."
        ),
        process_id=process_id,
    )
    comparison = compare_screenings(initial, document)
    assert comparison.initial_state is ScreeningStatus.PENDING
    assert comparison.document_state is ScreeningStatus.CANDIDATE
    assert comparison.diverged is True
    assert comparison.document_reason is DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE


def test_same_state_is_not_divergence() -> None:
    process_id = uuid4()
    text = "Manutenção preventiva de aparelhos de ar condicionado."
    initial = replace(screen(text), process_id=process_id)
    document = replace(screen_pages(text), process_id=process_id)
    comparison = compare_screenings(initial, document)
    assert comparison.initial_state is ScreeningStatus.CANDIDATE
    assert comparison.document_state is ScreeningStatus.CANDIDATE
    assert comparison.diverged is False
