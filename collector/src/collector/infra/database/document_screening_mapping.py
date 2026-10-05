"""Tradução entre avaliação documental e linhas de persistência."""

from __future__ import annotations

from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import (
    DocumentCoverage,
    DocumentScreeningEvaluation,
    DocumentScreeningEvidence,
)
from collector.domain import ScreeningStatus


def document_evaluation_from_row(
    *,
    id,
    process_id,
    profile_id,
    profile_code: str,
    profile_version: str,
    state: str,
    reason_code: str,
    reason_text: str,
    evaluated_at,
    engine_version: str,
    document_set_fingerprint: str,
    documents_considered: int,
    sources_considered: int,
    pages_considered: int,
    pages_with_text: int,
    likely_scanned_sources: int,
    failed_sources: int,
    unsupported_sources: int,
    complete: bool,
    evidence_rows: list,
) -> DocumentScreeningEvaluation:
    evidence = tuple(
        DocumentScreeningEvidence(
            category=row.category,
            configured_term=row.configured_term,
            matched_text=row.matched_text,
            context_snippet=row.context_snippet,
            page_number=row.page_number,
            extraction_page_id=row.extraction_page_id,
            source_id=row.source_id,
            source_sha256=row.source_sha256,
            source_path=row.source_path,
            artifact_id=row.artifact_id,
            artifact_sha256=row.artifact_sha256,
            document_id=row.document_id,
            negated=row.negated,
            start_offset=row.start_offset,
            end_offset=row.end_offset,
            token_start=0,
            token_end=0,
        )
        for row in evidence_rows
    )
    return DocumentScreeningEvaluation(
        id=id,
        process_id=process_id,
        profile_id=profile_id,
        profile_code=profile_code,
        profile_version=profile_version,
        state=ScreeningStatus(state),
        reason_code=DocumentReasonCode(reason_code),
        reason_text=reason_text,
        evaluated_at=evaluated_at,
        engine_version=engine_version,
        document_set_fingerprint=document_set_fingerprint,
        coverage=DocumentCoverage(
            documents_considered=documents_considered,
            sources_considered=sources_considered,
            pages_considered=pages_considered,
            pages_with_text=pages_with_text,
            likely_scanned_sources=likely_scanned_sources,
            failed_sources=failed_sources,
            unsupported_sources=unsupported_sources,
            complete=complete,
        ),
        evidence=evidence,
    )
