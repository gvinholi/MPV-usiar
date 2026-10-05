"""Motor documental: positivos, mistos, exclusões, ausência e negação."""

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.domain import ScreeningStatus
from tests.application.document_screening.helpers import corpus_from_pages, screen_pages
from collector.application.document_screening.engine import DocumentScreeningEngine
from collector.application.screening.profiles import usiar_v1


def test_candidate_maintenance() -> None:
    result = screen_pages(
        "Contratação de empresa para execução de manutenção preventiva e "
        "corretiva dos aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE
    assert result.state not in {ScreeningStatus.SELECTED, ScreeningStatus.CONFIRMED}


def test_pending_mixed_supply() -> None:
    result = screen_pages(
        "Prestação de serviços de manutenção preventiva e fornecimento de "
        "peças para sistemas de climatização."
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_SUPPLY


def test_discarded_isolated_installation() -> None:
    result = screen_pages("Serviço de instalação de aparelhos de ar condicionado.")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is DocumentReasonCode.DOCUMENT_ISOLATED_INSTALLATION


def test_discarded_isolated_purchase() -> None:
    result = screen_pages("Aquisição de condicionadores de ar.")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is DocumentReasonCode.DOCUMENT_ISOLATED_EQUIPMENT_PURCHASE


def test_discarded_isolated_parts() -> None:
    result = screen_pages("Fornecimento de peças para equipamentos de climatização.")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is DocumentReasonCode.DOCUMENT_ISOLATED_PARTS_SUPPLY


def test_no_evidence_is_pending_not_discarded() -> None:
    result = screen_pages("Regras para apresentação da proposta.")
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_NO_DECISIVE_EVIDENCE


def test_context_without_service_is_pending() -> None:
    result = screen_pages("Objeto: sistema de climatização do prédio sede.")
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT


def test_negation_does_not_create_mixed_supply() -> None:
    result = screen_pages(
        "Manutenção preventiva dos aparelhos de ar condicionado. "
        "Não haverá fornecimento de equipamentos."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE
    assert any(
        item.negated and item.category in {"purchase", "parts"} for item in result.evidence
    )


def test_negation_does_not_create_mixed_installation() -> None:
    result = screen_pages(
        "Manutenção corretiva dos aparelhos de ar condicionado. "
        "Os serviços não incluem instalação."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE


def test_sanitization_candidate() -> None:
    result = screen_pages(
        "Contratação de higienização de aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is DocumentReasonCode.DOCUMENT_RELEVANT_SANITIZATION


def test_likely_scanned_blocks_isolated_discard() -> None:
    result = screen_pages(
        "Serviço de instalação de aparelhos de ar condicionado.",
        status="LIKELY_SCANNED",
        likely_scanned=True,
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_INCOMPLETE_COVERAGE
    assert result.coverage.complete is False


def test_failed_source_marks_incomplete() -> None:
    engine = DocumentScreeningEngine()
    corpus = corpus_from_pages(
        "Regras para apresentação da proposta.",
        status="FAILED",
    )
    result = engine.evaluate(usiar_v1(), corpus)
    assert result.coverage.complete is False
    assert result.coverage.failed_sources == 1
    assert result.state is ScreeningStatus.PENDING


def test_no_pages_is_pending() -> None:
    engine = DocumentScreeningEngine()
    empty = corpus_from_pages()
    empty = type(empty)(process_id=empty.process_id, pages=(), sources=empty.sources)
    result = engine.evaluate(usiar_v1(), empty)
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_NO_TEXT


def test_filename_is_not_used_for_decision() -> None:
    result = screen_pages(
        "Regras para apresentação da proposta.",
        source_sha256="aa" * 32,
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is DocumentReasonCode.DOCUMENT_NO_DECISIVE_EVIDENCE
