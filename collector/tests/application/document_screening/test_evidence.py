"""Evidência aponta página, termo, snippet original e proveniência."""

from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.snippet import context_snippet
from tests.application.document_screening.helpers import page_ref, screen_pages


def test_evidence_has_page_term_snippet_and_source() -> None:
    result = screen_pages(
        "Contratação de empresa para execução de manutenção preventiva e "
        "corretiva dos aparelhos de ar condicionado."
    )
    maintenance = next(
        item for item in result.evidence if item.category == "maintenance"
    )
    context = next(item for item in result.evidence if item.category == "context")
    assert maintenance.page_number == 1
    assert maintenance.extraction_page_id
    assert "manutenção" in maintenance.matched_text.lower()
    assert maintenance.configured_term
    assert "manutenção" in maintenance.context_snippet.lower()
    assert maintenance.context_snippet != result.evidence[0].__class__.__doc__
    assert maintenance.source_sha256
    assert maintenance.source_path == "edital.pdf"
    assert maintenance.artifact_id
    assert context.page_number == 1
    assert "ar condicionado" in context.matched_text.lower()


def test_snippet_comes_from_original_not_normalized() -> None:
    text = "Prestação de serviços de Manutenção Preventiva dos aparelhos de ar-condicionado."
    result = screen_pages(text)
    hit = next(item for item in result.evidence if item.category == "maintenance")
    assert "Manutenção" in hit.matched_text or "manutenção" in hit.matched_text.lower()
    assert text[hit.start_offset : hit.end_offset] == hit.matched_text
    assert hit.matched_text in text
    assert hit.context_snippet.replace("...", "") in text or hit.matched_text in text


def test_snippet_is_not_the_whole_page() -> None:
    body = "x" * 400 + " manutenção preventiva dos aparelhos de ar condicionado " + "y" * 400
    result = screen_pages(body)
    hit = next(item for item in result.evidence if item.category == "maintenance")
    assert len(hit.context_snippet) <= 320
    assert len(hit.context_snippet) < len(body)
    assert "manutenção preventiva" in hit.context_snippet.lower()


def test_second_page_evidence_keeps_page_number() -> None:
    result = screen_pages(
        "Regras para apresentação da proposta.",
        "Higienização de aparelhos de ar condicionado.",
    )
    hit = next(item for item in result.evidence if item.category == "sanitization")
    assert hit.page_number == 2


def test_snippet_does_not_split_combining_mark() -> None:
    text = "manutenção"
    snippet = context_snippet(text, 0, len(text), DocumentScreeningPolicy())
    assert snippet == text


def test_page_ref_provenance_is_preserved() -> None:
    page = page_ref(
        "Manutenção preventiva de aparelhos de ar condicionado.",
        source_path="PE041-26.pdf",
    )
    from collector.application.document_screening.engine import DocumentScreeningEngine
    from collector.application.document_screening.results import (
        DocumentScreeningCorpus,
        DocumentSourceRef,
    )
    from collector.application.screening.profiles import usiar_v1

    corpus = DocumentScreeningCorpus(
        process_id=page.artifact_id,
        pages=(page,),
        sources=(
            DocumentSourceRef(
                source_id=page.source_id,
                source_sha256=page.source_sha256,
                source_path=page.source_path,
                artifact_id=page.artifact_id,
                artifact_sha256=page.artifact_sha256,
                status="DIGITAL_TEXT",
                likely_scanned=False,
                page_count=1,
                pages_with_text=1,
                document_id=page.document_id,
            ),
        ),
    )
    result = DocumentScreeningEngine().evaluate(usiar_v1(), corpus)
    assert result.evidence[0].source_path == "PE041-26.pdf"
    assert result.evidence[0].source_id == page.source_id
    assert result.evidence[0].extraction_page_id == page.extraction_page_id
