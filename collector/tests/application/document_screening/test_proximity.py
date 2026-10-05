"""Proximidade: mesma página e janela de 80 tokens. Páginas distintas não combinam."""

from collector.application.document_screening.policy import (
    DEFAULT_PROXIMITY_TOKEN_WINDOW,
    DocumentScreeningPolicy,
)
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.domain import ScreeningStatus
from tests.application.document_screening.helpers import screen_pages


def test_same_sentence_is_proximate() -> None:
    result = screen_pages(
        "Manutenção preventiva dos aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert DEFAULT_PROXIMITY_TOKEN_WINDOW == 80


def test_same_paragraph_is_proximate() -> None:
    result = screen_pages(
        "A contratada executará manutenção preventiva e corretiva. "
        "O objeto cobre os aparelhos de ar condicionado do prédio."
    )
    assert result.state is ScreeningStatus.CANDIDATE


def test_same_page_near_is_proximate() -> None:
    filler = " cláusula contratual complementar " * 8
    result = screen_pages(
        f"Manutenção preventiva.{filler}aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE


def test_same_page_far_is_not_combined() -> None:
    filler = " cláusula contratual complementar " * 40
    result = screen_pages(
        f"Manutenção preventiva e corretiva.{filler}aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT


def test_different_pages_are_not_combined() -> None:
    result = screen_pages(
        "Contratação de manutenção predial e serviços continuados de manutenção.",
        "Cláusula isolada sobre aparelhos de ar condicionado em outro anexo.",
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT


def test_narrow_window_rejects_near_but_outside() -> None:
    policy = DocumentScreeningPolicy(proximity_token_window=0)
    result = screen_pages(
        "Manutenção preventiva dos aparelhos de ar condicionado.",
        policy=policy,
    )
    assert result.state is ScreeningStatus.PENDING
