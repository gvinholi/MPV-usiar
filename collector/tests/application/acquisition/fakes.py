"""Fakes da aquisição — sem HTTP real e sem PostgreSQL."""

from __future__ import annotations

import io
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.acquisition.ports import DownloadMetadata, StoragePutResult
from collector.application.acquisition.results import DocumentAcquisitionResult
from collector.domain.artifact import ArchiveEntry, Artifact


class FakeDownload:
    def __init__(self, body: bytes, metadata: DownloadMetadata) -> None:
        self.metadata = metadata
        self.body = body
        self.closed = False

    def iter_chunks(self) -> Iterator[bytes]:
        for index in range(0, len(self.body), 5):
            yield self.body[index : index + 5]

    def close(self) -> None:
        self.closed = True


class FakeDownloader:
    def __init__(
        self,
        body: bytes = b"",
        error: BaseException | None = None,
        *,
        content_type: str | None = "application/octet-stream",
        content_length: int | None = None,
        filename: str | None = None,
        status_code: int = 200,
        final_url: str | None = None,
    ) -> None:
        self.body = body
        self.error = error
        self.content_type = content_type
        self.content_length = content_length
        self.filename = filename
        self.status_code = status_code
        self.final_url = final_url
        self.calls: list[str] = []

    def open(self, url: str) -> FakeDownload:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return FakeDownload(
            self.body,
            DownloadMetadata(
                requested_url=url,
                final_url=self.final_url or url,
                status_code=self.status_code,
                content_type=self.content_type,
                content_length=self.content_length,
                original_filename=self.filename,
            ),
        )


class MemoryTemp:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.discarded = False

    def write(self, chunk: bytes) -> None:
        self.buf.extend(chunk)

    def size(self) -> int:
        return len(self.buf)

    def open_read(self):
        return io.BytesIO(bytes(self.buf))

    def discard(self) -> None:
        self.discarded = True


class MemoryStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.temps: list[MemoryTemp] = []

    def open_temp(self) -> MemoryTemp:
        temp = MemoryTemp()
        self.temps.append(temp)
        return temp

    def commit(self, temp: MemoryTemp, *, sha256: str) -> StoragePutResult:
        created = sha256 not in self.blobs
        self.blobs[sha256] = bytes(temp.buf)
        return StoragePutResult(
            storage_key=f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}",
            created=created,
        )

    def exists(self, sha256: str) -> bool:
        return sha256 in self.blobs

    def open(self, storage_key: str):
        digest = storage_key.rsplit("/", 1)[-1]
        return io.BytesIO(self.blobs[digest])

    def delete_if_created(self, storage_key: str) -> None:
        digest = storage_key.rsplit("/", 1)[-1]
        self.blobs.pop(digest, None)


class InMemoryAcquisitionRepository:
    def __init__(self) -> None:
        self.artifacts: dict[str, Artifact] = {}
        self.acquisitions: list[DocumentAcquisitionResult] = []
        self.entries: dict[UUID, tuple[ArchiveEntry, ...]] = {}

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def find_artifact_by_sha256(self, sha256: str) -> Artifact | None:
        return self.artifacts.get(sha256)

    def insert_artifact(self, artifact: Artifact, *, created_at: datetime) -> None:
        del created_at
        self.artifacts[artifact.sha256] = artifact

    def insert_acquisition(
        self, result: DocumentAcquisitionResult, *, created_at: datetime
    ) -> None:
        del created_at
        self.acquisitions.append(result)

    def insert_archive_entries(
        self,
        artifact_id: UUID,
        entries: tuple[ArchiveEntry, ...],
        *,
        created_at: datetime,
    ) -> None:
        del created_at
        self.entries[artifact_id] = entries

    def has_archive_entries(self, artifact_id: UUID) -> bool:
        return artifact_id in self.entries
