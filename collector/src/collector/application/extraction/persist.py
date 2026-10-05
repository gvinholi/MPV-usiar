"""Persiste extrações textuais. Sem filesystem e sem parser PDF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.extraction.ports import TextExtractionRepository
from collector.application.extraction.results import ArtifactTextExtractionResult, SourceExtraction
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


@dataclass(frozen=True)
class PersistTextExtractionOutcome:
    sources_created: int
    extractions_created: int
    pages_created: int


class PersistTextExtraction:
    def __init__(
        self,
        repository: TextExtractionRepository,
        *,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def persist(self, result: ArtifactTextExtractionResult) -> PersistTextExtractionOutcome:
        with self._repository.transaction():
            now = result.finished_at or self._clock()
            sources_created = 0
            extractions_created = 0
            pages_created = 0
            for item in result.sources:
                source = item.source
                entry_id = source.archive_entry_id or self._repository.find_archive_entry_id(
                    source.artifact_id, source.source_path
                )
                if entry_id is not None and source.archive_entry_id != entry_id:
                    source = replace(source, archive_entry_id=entry_id)
                    item = replace(item, source=source)
                found = self._repository.find_source(
                    source.artifact_id, source.source_path, source.sha256
                )
                if found is None:
                    self._repository.insert_source(source, created_at=now)
                    sources_created += 1
                    source_id = source.id
                else:
                    source_id = found.id
                    item = replace(item, source=replace(source, id=source_id))
                existing = self._repository.find_extraction_id(
                    source_id, result.extractor_name, result.extractor_version
                )
                if existing is not None:
                    continue
                extraction_id = self._new_id()
                self._repository.insert_extraction(
                    extraction_id,
                    item,
                    extractor_name=result.extractor_name,
                    extractor_version=result.extractor_version,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                    created_at=now,
                )
                self._repository.insert_pages(
                    extraction_id, item.pages, created_at=now
                )
                extractions_created += 1
                pages_created += len(item.pages)
            return PersistTextExtractionOutcome(
                sources_created=sources_created,
                extractions_created=extractions_created,
                pages_created=pages_created,
            )
