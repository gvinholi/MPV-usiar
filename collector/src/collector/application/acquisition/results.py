"""Resultado auditável de uma aquisição. Não é path de arquivo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.acquisition.reasons import AcquisitionReason
from collector.domain.artifact import ArchiveEntry, Artifact, FileType


@dataclass(frozen=True)
class AcquisitionIssue:
    reason: AcquisitionReason
    message: str


@dataclass(frozen=True)
class ArchiveSummary:
    entry_count: int
    total_compressed_bytes: int
    total_uncompressed_bytes: int
    safe: bool
    flags: tuple[AcquisitionReason, ...]
    entries: tuple[ArchiveEntry, ...]


@dataclass(frozen=True)
class DocumentAcquisitionResult:
    document_id: UUID
    acquisition_id: UUID
    complete: bool
    artifact: Artifact | None
    requested_url: str | None
    final_url: str | None
    bytes_received: int
    sha256: str | None
    detected_type: FileType | None
    http_status: int | None
    http_content_type: str | None
    content_length: int | None
    original_filename: str | None
    archive: ArchiveSummary | None
    errors: tuple[AcquisitionIssue, ...]
    acquired_at: datetime
    storage_created: bool = False
    blob_reused: bool = False
