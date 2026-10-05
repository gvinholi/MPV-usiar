"""Fakes da extração — sem pypdf obrigatório no caso de uso."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.results import SourceExtraction
from collector.domain.text import TextPage, TextSource


class FakeExtractor:
    def __init__(
        self,
        pages: tuple[TextPage, ...] | None = None,
        error: ExtractionError | None = None,
        *,
        name: str = "pypdf",
        version: str = "test",
    ) -> None:
        self.name = name
        self.version = version
        self.pages = pages
        self.error = error

    def extract_pages(self, stream) -> tuple[TextPage, ...]:
        del stream
        if self.error is not None:
            raise self.error
        return self.pages or ()


class InMemoryTextRepository:
    def __init__(self) -> None:
        self.sources: dict[tuple[UUID, str, str], TextSource] = {}
        self.entries: dict[tuple[UUID, str], UUID] = {}
        self.extractions: dict[tuple[UUID, str, str], UUID] = {}
        self.pages: dict[UUID, tuple[TextPage, ...]] = {}

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def find_source(self, artifact_id, source_path, sha256):
        return self.sources.get((artifact_id, source_path, sha256))

    def find_archive_entry_id(self, artifact_id, original_path):
        return self.entries.get((artifact_id, original_path))

    def insert_source(self, source: TextSource, *, created_at: datetime) -> None:
        del created_at
        self.sources[(source.artifact_id, source.source_path, source.sha256)] = source

    def find_extraction_id(self, source_id, extractor_name, extractor_version):
        return self.extractions.get((source_id, extractor_name, extractor_version))

    def insert_extraction(
        self,
        extraction_id: UUID,
        item: SourceExtraction,
        *,
        extractor_name: str,
        extractor_version: str,
        started_at,
        finished_at,
        created_at,
    ) -> None:
        del started_at, finished_at, created_at
        self.extractions[
            (item.source.id, extractor_name, extractor_version)
        ] = extraction_id

    def insert_pages(self, extraction_id, pages, *, created_at) -> None:
        del created_at
        self.pages[extraction_id] = pages
