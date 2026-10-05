"""Repositório PostgreSQL de artefatos e aquisições."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.acquisition.results import DocumentAcquisitionResult
from collector.application.persistence.errors import PersistenceError
from collector.domain.artifact import ArchiveEntry, Artifact, FileType
from collector.infra.database.models import (
    ArtifactArchiveEntryRow,
    ArtifactRow,
    DocumentArtifactRow,
)


class SqlAlchemyDocumentAcquisitionRepository:
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

    def find_artifact_by_sha256(self, sha256: str) -> Artifact | None:
        row = self._require_session().scalar(
            select(ArtifactRow).where(ArtifactRow.sha256 == sha256)
        )
        if row is None:
            return None
        return Artifact(
            id=row.id,
            sha256=row.sha256,
            size_bytes=row.size_bytes,
            detected_type=FileType(row.detected_type),
            storage_key=row.storage_key,
            hash_algorithm=row.hash_algorithm,
        )

    def insert_artifact(self, artifact: Artifact, *, created_at: datetime) -> None:
        session = self._require_session()
        session.add(
            ArtifactRow(
                id=artifact.id,
                sha256=artifact.sha256,
                hash_algorithm=artifact.hash_algorithm,
                size_bytes=artifact.size_bytes,
                detected_type=artifact.detected_type.value,
                storage_key=artifact.storage_key,
                created_at=created_at,
            )
        )
        session.flush()

    def insert_acquisition(
        self, result: DocumentAcquisitionResult, *, created_at: datetime
    ) -> None:
        reason = result.errors[0].reason.value if result.errors else None
        self._require_session().add(
            DocumentArtifactRow(
                id=result.acquisition_id,
                document_id=result.document_id,
                artifact_id=None if result.artifact is None else result.artifact.id,
                acquired_at=result.acquired_at,
                requested_url=result.requested_url,
                final_url=result.final_url,
                http_status=result.http_status,
                http_content_type=result.http_content_type,
                original_filename=result.original_filename,
                complete=result.complete,
                reason_code=None if result.complete else reason,
                bytes_received=result.bytes_received,
                created_at=created_at,
            )
        )

    def insert_archive_entries(
        self,
        artifact_id: UUID,
        entries: tuple[ArchiveEntry, ...],
        *,
        created_at: datetime,
    ) -> None:
        session = self._require_session()
        for entry in entries:
            session.add(
                ArtifactArchiveEntryRow(
                    id=uuid4(),
                    artifact_id=artifact_id,
                    original_path=entry.original_path,
                    compressed_size=entry.compressed_size,
                    uncompressed_size=entry.uncompressed_size,
                    is_directory=entry.is_directory,
                    extension=entry.extension,
                    is_encrypted=entry.is_encrypted,
                    is_symlink=entry.is_symlink,
                    has_unsafe_path=entry.has_unsafe_path,
                    unsafe_path_reason=entry.unsafe_path_reason,
                    created_at=created_at,
                )
            )

    def has_archive_entries(self, artifact_id: UUID) -> bool:
        row = self._require_session().scalar(
            select(ArtifactArchiveEntryRow.id).where(
                ArtifactArchiveEntryRow.artifact_id == artifact_id
            )
        )
        return row is not None

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
