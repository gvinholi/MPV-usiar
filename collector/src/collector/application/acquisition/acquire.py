"""Adquire um documento já catalogado. Sem coleta e sem triagem."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.acquisition.errors import AcquisitionError
from collector.application.acquisition.filetype import detect_file_type
from collector.application.acquisition.policy import DocumentAcquisitionPolicy
from collector.application.acquisition.ports import ArtifactStorage, BinaryDownloader, TempBlob
from collector.application.acquisition.reasons import AcquisitionReason
from collector.application.acquisition.results import (
    AcquisitionIssue,
    ArchiveSummary,
    DocumentAcquisitionResult,
)
from collector.application.acquisition.zipinspect import inspect_zip
from collector.domain import ProcurementDocument
from collector.domain.artifact import HASH_ALGORITHM_SHA256, Artifact, FileType
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


class AcquireDocumentArtifact:
    def __init__(
        self,
        downloader: BinaryDownloader,
        storage: ArtifactStorage,
        *,
        policy: DocumentAcquisitionPolicy | None = None,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._downloader = downloader
        self._storage = storage
        self._policy = policy or DocumentAcquisitionPolicy()
        self._clock = clock
        self._new_id = new_id

    def acquire(self, document: ProcurementDocument) -> DocumentAcquisitionResult:
        acquired_at = self._clock()
        acquisition_id = self._new_id()
        url = document.url
        if url is None or not url.strip():
            return _failed(
                document_id=document.id,
                acquisition_id=acquisition_id,
                acquired_at=acquired_at,
                reason=AcquisitionReason.MISSING_DOCUMENT_URL,
                message="documento catalogado sem URL de arquivo",
            )

        download = None
        temp: TempBlob | None = None
        try:
            download = self._downloader.open(url.strip())
            metadata = download.metadata
            if (
                metadata.content_length is not None
                and metadata.content_length > self._policy.max_download_bytes
            ):
                return _failed(
                    document_id=document.id,
                    acquisition_id=acquisition_id,
                    acquired_at=acquired_at,
                    reason=AcquisitionReason.DOWNLOAD_SIZE_LIMIT_EXCEEDED,
                    message="Content-Length excede o limite de download",
                    requested_url=metadata.requested_url,
                    final_url=metadata.final_url,
                    http_status=metadata.status_code,
                    http_content_type=metadata.content_type,
                    content_length=metadata.content_length,
                    original_filename=metadata.original_filename,
                )

            temp = self._storage.open_temp()
            hasher = hashlib.sha256()
            received = 0
            header = b""
            for chunk in download.iter_chunks():
                if not chunk:
                    continue
                if received + len(chunk) > self._policy.max_download_bytes:
                    raise AcquisitionError(
                        "bytes recebidos excedem o limite de download",
                        reason=AcquisitionReason.DOWNLOAD_SIZE_LIMIT_EXCEEDED,
                    )
                hasher.update(chunk)
                temp.write(chunk)
                received += len(chunk)
                if len(header) < 8:
                    header += chunk[: 8 - len(header)]

            if received == 0:
                return _failed(
                    document_id=document.id,
                    acquisition_id=acquisition_id,
                    acquired_at=acquired_at,
                    reason=AcquisitionReason.EMPTY_FILE,
                    message="resposta HTTP sem bytes",
                    requested_url=metadata.requested_url,
                    final_url=metadata.final_url,
                    http_status=metadata.status_code,
                    http_content_type=metadata.content_type,
                    content_length=metadata.content_length,
                    original_filename=metadata.original_filename,
                )

            digest = hasher.hexdigest()
            detected = detect_file_type(header)
            archive = _inspect_if_zip(detected, temp, self._policy)
            put = self._storage.commit(temp, sha256=digest)
            temp = None
            artifact = Artifact(
                id=self._new_id(),
                sha256=digest,
                size_bytes=received,
                detected_type=detected,
                storage_key=put.storage_key,
                hash_algorithm=HASH_ALGORITHM_SHA256,
            )
            issues = tuple(
                AcquisitionIssue(reason=flag, message=flag.value)
                for flag in (archive.flags if archive is not None else ())
            )
            return DocumentAcquisitionResult(
                document_id=document.id,
                acquisition_id=acquisition_id,
                complete=True,
                artifact=artifact,
                requested_url=metadata.requested_url,
                final_url=metadata.final_url,
                bytes_received=received,
                sha256=digest,
                detected_type=detected,
                http_status=metadata.status_code,
                http_content_type=metadata.content_type,
                content_length=metadata.content_length,
                original_filename=metadata.original_filename,
                archive=archive,
                errors=issues,
                acquired_at=acquired_at,
                storage_created=put.created,
                blob_reused=not put.created,
            )
        except AcquisitionError as exc:
            return _failed(
                document_id=document.id,
                acquisition_id=acquisition_id,
                acquired_at=acquired_at,
                reason=exc.reason,
                message=str(exc),
                requested_url=url,
            )
        finally:
            if download is not None:
                download.close()
            if temp is not None:
                temp.discard()


def _inspect_if_zip(
    detected: FileType, temp: TempBlob, policy: DocumentAcquisitionPolicy
) -> ArchiveSummary | None:
    if detected is not FileType.ZIP:
        return None
    with temp.open_read() as stream:
        return inspect_zip(stream, policy)


def _failed(
    *,
    document_id: UUID,
    acquisition_id: UUID,
    acquired_at: datetime,
    reason: AcquisitionReason,
    message: str,
    requested_url: str | None = None,
    final_url: str | None = None,
    http_status: int | None = None,
    http_content_type: str | None = None,
    content_length: int | None = None,
    original_filename: str | None = None,
) -> DocumentAcquisitionResult:
    return DocumentAcquisitionResult(
        document_id=document_id,
        acquisition_id=acquisition_id,
        complete=False,
        artifact=None,
        requested_url=requested_url,
        final_url=final_url,
        bytes_received=0,
        sha256=None,
        detected_type=None,
        http_status=http_status,
        http_content_type=http_content_type,
        content_length=content_length,
        original_filename=original_filename,
        archive=None,
        errors=(AcquisitionIssue(reason=reason, message=message),),
        acquired_at=acquired_at,
    )
