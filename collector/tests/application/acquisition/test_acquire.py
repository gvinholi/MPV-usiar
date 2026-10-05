"""Aquisição explícita — sem internet e sem triagem USIAR."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from collector.application import (
    AcquireDocumentArtifact,
    AcquisitionReason,
    DocumentAcquisitionPolicy,
    PersistDocumentAcquisition,
)
from collector.domain import ProcurementDocument, Source, SourceDocumentIdentity
from tests.application.acquisition.fakes import (
    FakeDownloader,
    InMemoryAcquisitionRepository,
    MemoryStorage,
)
from tests.application.acquisition.zip_fixtures import PDF_BYTES, UNKNOWN_BYTES, zip_bytes

CAPTURED = datetime(2026, 10, 4, 22, 0, tzinfo=UTC)
URL = "https://pncp.gov.br/pncp-api/v1/orgaos/00394502000144/compras/2026/12795/arquivos/1"


def _document(*, url: str | None = URL) -> ProcurementDocument:
    return ProcurementDocument(
        id=uuid4(),
        process_id=uuid4(),
        identity=SourceDocumentIdentity(
            source=Source.PNCP,
            official_id="00394502000144/2026/12795/1",
        ),
        title="Edital e Anexos PE SRP N285-2026.zip",
        url=url,
    )


def _acquire(body: bytes, **kwargs) -> AcquireDocumentArtifact:
    return AcquireDocumentArtifact(
        FakeDownloader(body, **kwargs),
        MemoryStorage(),
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024),
        clock=lambda: CAPTURED,
    )


def test_pdf_small() -> None:
    result = _acquire(PDF_BYTES).acquire(_document())
    assert result.complete is True
    assert result.detected_type.value == "PDF"
    assert result.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert result.bytes_received == len(PDF_BYTES)
    assert result.artifact is not None
    assert result.artifact.hash_algorithm == "sha256"


def test_zip_small() -> None:
    payload = zip_bytes(("a.pdf", PDF_BYTES))
    result = _acquire(payload).acquire(_document())
    assert result.complete is True
    assert result.detected_type.value == "ZIP"
    assert result.archive is not None
    assert result.archive.safe is True
    assert result.archive.entry_count == 1


def test_unknown_is_valid_download() -> None:
    result = _acquire(UNKNOWN_BYTES).acquire(_document())
    assert result.complete is True
    assert result.detected_type.value == "UNKNOWN"


def test_empty_file() -> None:
    result = _acquire(b"").acquire(_document())
    assert result.complete is False
    assert result.errors[0].reason is AcquisitionReason.EMPTY_FILE
    assert result.artifact is None


def test_content_length_over_limit_aborts() -> None:
    result = _acquire(PDF_BYTES, content_length=10_000).acquire(_document())
    assert result.complete is False
    assert result.errors[0].reason is AcquisitionReason.DOWNLOAD_SIZE_LIMIT_EXCEEDED


def test_stream_over_limit_ignores_small_content_length() -> None:
    body = b"x" * 80
    service = AcquireDocumentArtifact(
        FakeDownloader(body, content_length=10),
        MemoryStorage(),
        policy=DocumentAcquisitionPolicy(max_download_bytes=50),
        clock=lambda: CAPTURED,
    )
    result = service.acquire(_document())
    assert result.complete is False
    assert result.errors[0].reason is AcquisitionReason.DOWNLOAD_SIZE_LIMIT_EXCEEDED


def test_same_content_same_hash() -> None:
    service = _acquire(PDF_BYTES)
    first = service.acquire(_document())
    second = service.acquire(_document())
    assert first.sha256 == second.sha256


def test_different_content_different_hash() -> None:
    first = _acquire(PDF_BYTES).acquire(_document())
    second = _acquire(UNKNOWN_BYTES).acquire(_document())
    assert first.sha256 != second.sha256


def test_missing_url() -> None:
    result = _acquire(PDF_BYTES).acquire(_document(url=None))
    assert result.errors[0].reason is AcquisitionReason.MISSING_DOCUMENT_URL


def test_same_hash_reuses_blob_and_records_acquisition() -> None:
    storage = MemoryStorage()
    downloader = FakeDownloader(PDF_BYTES)
    service = AcquireDocumentArtifact(
        downloader,
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024),
        clock=lambda: CAPTURED,
    )
    document = _document()
    first = service.acquire(document)
    second = service.acquire(document)
    persist = PersistDocumentAcquisition(InMemoryAcquisitionRepository())
    persist.persist(first)
    outcome = persist.persist(second)
    assert first.storage_created is True
    assert second.blob_reused is True
    assert outcome.artifact_created is False
    assert outcome.acquisition_created is True
    assert len(storage.blobs) == 1


def test_temp_discarded_on_empty() -> None:
    storage = MemoryStorage()
    service = AcquireDocumentArtifact(
        FakeDownloader(b""),
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024),
        clock=lambda: CAPTURED,
    )
    service.acquire(_document())
    assert storage.temps[0].discarded is True
