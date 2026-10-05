"""Repositório PostgreSQL de extrações textuais."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.extraction.results import SourceExtraction
from collector.application.persistence.errors import PersistenceError
from collector.domain.artifact import FileType
from collector.domain.text import TextPage, TextSource
from collector.infra.database.models import (
    ArtifactArchiveEntryRow,
    ArtifactTextSourceRow,
    TextExtractionPageRow,
    TextExtractionRow,
)


class SqlAlchemyTextExtractionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @contextmanager
    def transaction(self):
        session = self._session_factory()
        self._session = session
        try:
            yield
            session.commit()
        except PersistenceError:
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise PersistenceError("falha inesperada na persistência") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            self._session = None

    def find_source(
        self, artifact_id: UUID, source_path: str, sha256: str
    ) -> TextSource | None:
        row = self._require_session().scalar(
            select(ArtifactTextSourceRow).where(
                ArtifactTextSourceRow.artifact_id == artifact_id,
                ArtifactTextSourceRow.source_path == source_path,
                ArtifactTextSourceRow.sha256 == sha256,
            )
        )
        if row is None:
            return None
        return TextSource(
            id=row.id,
            artifact_id=row.artifact_id,
            archive_entry_id=row.archive_entry_id,
            source_path=row.source_path,
            sha256=row.sha256,
            size_bytes=row.size_bytes,
            detected_type=FileType(row.detected_type),
        )

    def find_archive_entry_id(self, artifact_id: UUID, original_path: str) -> UUID | None:
        return self._require_session().scalar(
            select(ArtifactArchiveEntryRow.id).where(
                ArtifactArchiveEntryRow.artifact_id == artifact_id,
                ArtifactArchiveEntryRow.original_path == original_path,
            )
        )

    def insert_source(self, source: TextSource, *, created_at: datetime) -> None:
        session = self._require_session()
        session.add(
            ArtifactTextSourceRow(
                id=source.id,
                artifact_id=source.artifact_id,
                archive_entry_id=source.archive_entry_id,
                source_path=source.source_path,
                sha256=source.sha256,
                size_bytes=source.size_bytes,
                detected_type=source.detected_type.value,
                created_at=created_at,
            )
        )
        session.flush()

    def find_extraction_id(
        self, source_id: UUID, extractor_name: str, extractor_version: str
    ) -> UUID | None:
        return self._require_session().scalar(
            select(TextExtractionRow.id).where(
                TextExtractionRow.source_id == source_id,
                TextExtractionRow.extractor_name == extractor_name,
                TextExtractionRow.extractor_version == extractor_version,
            )
        )

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
    ) -> None:
        session = self._require_session()
        session.add(
            TextExtractionRow(
                id=extraction_id,
                source_id=item.source.id,
                extractor_name=extractor_name,
                extractor_version=extractor_version,
                status=item.status.value,
                page_count=item.page_count,
                pages_with_text=item.pages_with_text,
                character_count=item.character_count,
                likely_scanned=item.likely_scanned,
                started_at=started_at,
                finished_at=finished_at,
                error_code=None if item.error is None else item.error.reason.value,
                error_text=None if item.error is None else item.error.message,
                created_at=created_at,
            )
        )
        session.flush()

    def insert_pages(
        self,
        extraction_id: UUID,
        pages: tuple[TextPage, ...],
        *,
        created_at: datetime,
    ) -> None:
        session = self._require_session()
        for page in pages:
            session.add(
                TextExtractionPageRow(
                    id=uuid4(),
                    extraction_id=extraction_id,
                    page_number=page.page_number,
                    text=page.text,
                    char_count=page.char_count,
                    created_at=created_at,
                )
            )

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
