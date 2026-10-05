"""Atalhos de avaliação documental para testes."""

from uuid import uuid4

from collector.application.document_screening.engine import DocumentScreeningEngine
from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.results import (
    DocumentPageRef,
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
    DocumentSourceRef,
)
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.profiles import usiar_v1


def _digest(label: str) -> str:
    return (label.encode("utf-8").hex() + "0" * 64)[:64]


def page_ref(
    text: str,
    *,
    page_number: int = 1,
    source_sha256: str | None = None,
    source_path: str = "edital.pdf",
    document_id=None,
) -> DocumentPageRef:
    source = source_sha256 or _digest(f"source-{source_path}")
    artifact = _digest("artifact")
    page_id = uuid4()
    source_id = uuid4()
    artifact_id = uuid4()
    return DocumentPageRef(
        extraction_page_id=page_id,
        page_number=page_number,
        text=text,
        source_id=source_id,
        source_sha256=source,
        source_path=source_path,
        artifact_id=artifact_id,
        artifact_sha256=artifact,
        document_id=document_id,
    )


def corpus_from_pages(
    *texts: str,
    process_id=None,
    source_sha256: str | None = None,
    status: str = "DIGITAL_TEXT",
    likely_scanned: bool = False,
) -> DocumentScreeningCorpus:
    process = process_id or uuid4()
    pages = []
    shared_source = source_sha256 or _digest("member-a")
    source_id = uuid4()
    artifact_id = uuid4()
    artifact_sha = _digest("artifact")
    document_id = uuid4()
    for index, text in enumerate(texts, start=1):
        pages.append(
            DocumentPageRef(
                extraction_page_id=uuid4(),
                page_number=index,
                text=text,
                source_id=source_id,
                source_sha256=shared_source,
                source_path="edital.pdf",
                artifact_id=artifact_id,
                artifact_sha256=artifact_sha,
                document_id=document_id,
            )
        )
    source = DocumentSourceRef(
        source_id=source_id,
        source_sha256=shared_source,
        source_path="edital.pdf",
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha,
        status=status,
        likely_scanned=likely_scanned,
        page_count=len(pages),
        pages_with_text=sum(1 for page in pages if page.text.strip()),
        document_id=document_id,
    )
    return DocumentScreeningCorpus(process_id=process, pages=tuple(pages), sources=(source,))


def screen_pages(
    *texts: str,
    profile: ScreeningProfile | None = None,
    policy: DocumentScreeningPolicy | None = None,
    status: str = "DIGITAL_TEXT",
    likely_scanned: bool = False,
    source_sha256: str | None = None,
) -> DocumentScreeningEvaluation:
    return DocumentScreeningEngine(policy=policy).evaluate(
        profile or usiar_v1(),
        corpus_from_pages(
            *texts,
            source_sha256=source_sha256,
            status=status,
            likely_scanned=likely_scanned,
        ),
    )
