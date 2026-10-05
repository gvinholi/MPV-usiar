"""Resultado auditável da triagem documental. Independente da triagem inicial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.domain import ScreeningStatus


DOCUMENT_ENGINE_VERSION = "1"

ALLOWED_STATES = frozenset(
    {
        ScreeningStatus.CANDIDATE,
        ScreeningStatus.PENDING,
        ScreeningStatus.DISCARDED,
    }
)


@dataclass(frozen=True)
class DocumentPageRef:
    extraction_page_id: UUID
    page_number: int
    text: str
    source_id: UUID
    source_sha256: str
    source_path: str
    artifact_id: UUID
    artifact_sha256: str
    document_id: UUID | None = None


@dataclass(frozen=True)
class DocumentSourceRef:
    source_id: UUID
    source_sha256: str
    source_path: str
    artifact_id: UUID
    artifact_sha256: str
    status: str
    likely_scanned: bool
    page_count: int
    pages_with_text: int
    document_id: UUID | None = None


@dataclass(frozen=True)
class DocumentScreeningCorpus:
    """Conjunto de um processo/artefato. Nunca o banco inteiro."""

    process_id: UUID
    pages: tuple[DocumentPageRef, ...]
    sources: tuple[DocumentSourceRef, ...]


@dataclass(frozen=True)
class DocumentCoverage:
    documents_considered: int
    sources_considered: int
    pages_considered: int
    pages_with_text: int
    likely_scanned_sources: int
    failed_sources: int
    unsupported_sources: int
    complete: bool


@dataclass(frozen=True)
class DocumentScreeningEvidence:
    category: str
    configured_term: str
    matched_text: str
    context_snippet: str
    page_number: int
    extraction_page_id: UUID
    source_id: UUID
    source_sha256: str
    source_path: str
    artifact_id: UUID
    artifact_sha256: str
    document_id: UUID | None
    negated: bool
    start_offset: int
    end_offset: int
    token_start: int
    token_end: int


@dataclass(frozen=True)
class DocumentScreeningEvaluation:
    id: UUID
    process_id: UUID
    profile_code: str
    profile_version: str
    state: ScreeningStatus
    reason_code: DocumentReasonCode
    reason_text: str
    evaluated_at: datetime
    engine_version: str
    document_set_fingerprint: str
    coverage: DocumentCoverage
    evidence: tuple[DocumentScreeningEvidence, ...]
    profile_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.state not in ALLOWED_STATES:
            raise ValueError("triagem documental não atribui SELECTED nem CONFIRMED")
        if self.state is ScreeningStatus.SELECTED or self.state is ScreeningStatus.CONFIRMED:
            raise ValueError("triagem documental não atribui SELECTED nem CONFIRMED")


@dataclass(frozen=True)
class DocumentScreeningSummary:
    processes_evaluated: int
    candidate: int
    pending: int
    discarded: int
    evidence_count: int
    pages_considered: int
    documents_considered: int
    incomplete_evaluations: int
    divergences_from_initial: int


def summarize_document_evaluations(
    evaluations: tuple[DocumentScreeningEvaluation, ...] | list[DocumentScreeningEvaluation],
    *,
    divergences_from_initial: int = 0,
) -> DocumentScreeningSummary:
    candidate = pending = discarded = evidence_count = 0
    pages_considered = documents_considered = incomplete = 0
    for evaluation in evaluations:
        evidence_count += len(evaluation.evidence)
        pages_considered += evaluation.coverage.pages_considered
        documents_considered += evaluation.coverage.documents_considered
        if not evaluation.coverage.complete:
            incomplete += 1
        if evaluation.state is ScreeningStatus.CANDIDATE:
            candidate += 1
        elif evaluation.state is ScreeningStatus.PENDING:
            pending += 1
        elif evaluation.state is ScreeningStatus.DISCARDED:
            discarded += 1
    return DocumentScreeningSummary(
        processes_evaluated=len(evaluations),
        candidate=candidate,
        pending=pending,
        discarded=discarded,
        evidence_count=evidence_count,
        pages_considered=pages_considered,
        documents_considered=documents_considered,
        incomplete_evaluations=incomplete,
        divergences_from_initial=divergences_from_initial,
    )
