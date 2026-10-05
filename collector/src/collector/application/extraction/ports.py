"""Portas da extração textual. Sem biblioteca PDF e sem ORM."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.extraction.results import (
    ArtifactTextExtractionResult,
    SourceExtraction,
)
from collector.domain.text import TextPage, TextSource


class PdfTextExtractor(Protocol):
    name: str
    version: str

    def extract_pages(self, stream) -> tuple[TextPage, ...]: ...


class TextExtractionRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def find_source(
        self, artifact_id: UUID, source_path: str, sha256: str
    ) -> TextSource | None: ...

    def find_archive_entry_id(self, artifact_id: UUID, original_path: str) -> UUID | None: ...

    def insert_source(self, source: TextSource, *, created_at: datetime) -> None: ...

    def find_extraction_id(
        self, source_id: UUID, extractor_name: str, extractor_version: str
    ) -> UUID | None: ...

    def insert_extraction(
        self,
        extraction_id: UUID,
        item: SourceExtraction,
        *,
        extractor_name: str,
        extractor_version: str,
        started_at: datetime,
        finished_at: datetime,
        created_at: datetime,
    ) -> None: ...

    def insert_pages(
        self,
        extraction_id: UUID,
        pages: tuple[TextPage, ...],
        *,
        created_at: datetime,
    ) -> None: ...
