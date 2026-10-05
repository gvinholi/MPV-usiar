"""Resultado auditável da extração. Sem mudar triagem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.extraction.reasons import ExtractionReason
from collector.domain.text import ExtractionStatus, TextPage, TextSource


@dataclass(frozen=True)
class ExtractionIssue:
    reason: ExtractionReason
    message: str
    source_path: str | None = None


@dataclass(frozen=True)
class SourceExtraction:
    source: TextSource
    status: ExtractionStatus
    pages: tuple[TextPage, ...]
    page_count: int
    pages_with_text: int
    character_count: int
    likely_scanned: bool
    error: ExtractionIssue | None = None


@dataclass(frozen=True)
class ExtractionMetrics:
    files_considered: int
    files_extracted: int
    files_failed: int
    files_unsupported: int
    pages_total: int
    pages_with_text: int
    pages_without_text: int
    characters_extracted: int
    likely_scanned_files: int


@dataclass(frozen=True)
class ArtifactTextExtractionResult:
    artifact_id: UUID
    artifact_sha256: str
    complete: bool
    sources: tuple[SourceExtraction, ...]
    metrics: ExtractionMetrics
    errors: tuple[ExtractionIssue, ...]
    started_at: datetime
    finished_at: datetime
    extractor_name: str
    extractor_version: str
