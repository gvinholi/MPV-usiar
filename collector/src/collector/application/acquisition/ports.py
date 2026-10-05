"""Portas da aquisição. Sem cliente HTTP e sem ORM."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.acquisition.results import DocumentAcquisitionResult
from collector.domain.artifact import ArchiveEntry, Artifact


class DownloadMetadata:
    def __init__(
        self,
        *,
        requested_url: str,
        final_url: str,
        status_code: int,
        content_type: str | None,
        content_length: int | None,
        original_filename: str | None,
    ) -> None:
        self.requested_url = requested_url
        self.final_url = final_url
        self.status_code = status_code
        self.content_type = content_type
        self.content_length = content_length
        self.original_filename = original_filename


class BinaryDownload(Protocol):
    metadata: DownloadMetadata

    def iter_chunks(self) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class BinaryDownloader(Protocol):
    def open(self, url: str) -> BinaryDownload: ...


class TempBlob(Protocol):
    def write(self, chunk: bytes) -> None: ...

    def size(self) -> int: ...

    def open_read(self): ...

    def discard(self) -> None: ...


class StoragePutResult:
    def __init__(self, *, storage_key: str, created: bool) -> None:
        self.storage_key = storage_key
        self.created = created


class ArtifactStorage(Protocol):
    def open_temp(self) -> TempBlob: ...

    def commit(self, temp: TempBlob, *, sha256: str) -> StoragePutResult: ...

    def exists(self, sha256: str) -> bool: ...

    def open(self, storage_key: str): ...

    def delete_if_created(self, storage_key: str) -> None: ...


class DocumentAcquisitionRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def find_artifact_by_sha256(self, sha256: str) -> Artifact | None: ...

    def insert_artifact(self, artifact: Artifact, *, created_at: datetime) -> None: ...

    def insert_acquisition(
        self, result: DocumentAcquisitionResult, *, created_at: datetime
    ) -> None: ...

    def insert_archive_entries(
        self,
        artifact_id: UUID,
        entries: tuple[ArchiveEntry, ...],
        *,
        created_at: datetime,
    ) -> None: ...

    def has_archive_entries(self, artifact_id: UUID) -> bool: ...
