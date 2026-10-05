"""Extração textual em memória — sem rede."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from collector.application import (
    ExtractArtifactText,
    ExtractionReason,
    PersistTextExtraction,
    TextExtractionPolicy,
)
from collector.application.extraction.errors import ExtractionError
from collector.domain import Artifact, FileType, TextPage
from collector.infra.extraction import PypdfTextExtractor
from tests.application.acquisition.fakes import MemoryStorage
from tests.application.acquisition.zip_fixtures import zip_bytes
from tests.application.extraction.fakes import FakeExtractor, InMemoryTextRepository
from tests.application.extraction.pdf_fixtures import (
    FAKE_PDF_HEADER,
    INVALID_BYTES,
    ONE_PAGE_PDF,
    TWO_PAGE_PDF,
    text_pdf,
)

CAPTURED = datetime(2026, 10, 4, 23, 0, tzinfo=UTC)


def _put(storage: MemoryStorage, payload: bytes, detected: FileType) -> Artifact:
    digest = hashlib.sha256(payload).hexdigest()
    temp = storage.open_temp()
    temp.write(payload)
    put = storage.commit(temp, sha256=digest)
    return Artifact(
        id=uuid4(),
        sha256=digest,
        size_bytes=len(payload),
        detected_type=detected,
        storage_key=put.storage_key,
    )


def _service(storage, extractor, **policy):
    return ExtractArtifactText(
        storage,
        extractor,
        policy=TextExtractionPolicy(**policy) if policy else TextExtractionPolicy(),
        clock=lambda: CAPTURED,
    )


def test_one_page_pdf() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, ONE_PAGE_PDF, FileType.PDF)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.complete is True
    assert result.sources[0].page_count == 1
    assert result.sources[0].pages[0].page_number == 1
    assert "Hello page one" in result.sources[0].pages[0].text
    assert result.sources[0].source.sha256 == artifact.sha256
    assert result.sources[0].source.source_path == f"artifact:{artifact.sha256}"


def test_multiple_pages() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, TWO_PAGE_PDF, FileType.PDF)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert [page.page_number for page in result.sources[0].pages] == [1, 2]
    assert "First page" in result.sources[0].pages[0].text
    assert "Second page" in result.sources[0].pages[1].text


def test_empty_page_is_likely_scanned() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, text_pdf(""), FileType.PDF)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.sources[0].likely_scanned is True
    assert result.sources[0].status.value == "LIKELY_SCANNED"
    assert result.sources[0].page_count == 1


def test_invalid_pdf() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, INVALID_BYTES, FileType.UNKNOWN)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.complete is False
    assert result.errors[0].reason is ExtractionReason.UNSUPPORTED_FORMAT


def test_fake_pdf_signature() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, FAKE_PDF_HEADER, FileType.PDF)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.sources[0].status.value == "FAILED"
    assert result.sources[0].error is not None
    assert result.sources[0].error.reason is ExtractionReason.INVALID_PDF


def test_page_limit() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, TWO_PAGE_PDF, FileType.PDF)
    pages = (
        TextPage(1, "a" * 10, 10),
        TextPage(2, "b" * 10, 10),
        TextPage(3, "c" * 10, 10),
    )
    result = _service(storage, FakeExtractor(pages), max_pages_per_pdf=2).extract(artifact)
    assert result.sources[0].page_count == 2
    assert result.sources[0].error.reason is ExtractionReason.PDF_PAGE_LIMIT_EXCEEDED


def test_character_limit() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, ONE_PAGE_PDF, FileType.PDF)
    pages = (TextPage(1, "x" * 50, 50), TextPage(2, "y" * 50, 50))
    result = _service(storage, FakeExtractor(pages), max_chars_per_pdf=60).extract(artifact)
    assert result.sources[0].page_count == 1
    assert result.sources[0].error.reason is ExtractionReason.TEXT_CHARACTER_LIMIT_EXCEEDED


def test_zip_with_one_pdf() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("edital.pdf", ONE_PAGE_PDF))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.complete is True
    assert result.sources[0].source.source_path == "edital.pdf"
    assert result.sources[0].source.sha256 == hashlib.sha256(ONE_PAGE_PDF).hexdigest()


def test_zip_with_several_pdfs() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("a.pdf", ONE_PAGE_PDF), ("b.pdf", TWO_PAGE_PDF))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.metrics.files_extracted == 2
    assert result.metrics.pages_total == 3


def test_zip_pdf_and_txt() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("a.pdf", ONE_PAGE_PDF), ("notes.txt", b"hello"))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.metrics.files_extracted == 1
    assert result.metrics.files_unsupported == 1
    assert result.complete is False


def test_zip_subdirectory_pdf() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("pasta/edital.pdf", ONE_PAGE_PDF))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.sources[0].source.source_path == "pasta/edital.pdf"


def test_unsafe_zip_is_not_processed() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("../../etc/passwd", ONE_PAGE_PDF))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.complete is False
    assert any(issue.reason is ExtractionReason.UNSAFE_ARCHIVE for issue in result.errors)
    assert result.sources == ()


def test_member_named_pdf_but_not_pdf() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("falso.pdf", b"not-pdf"))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.sources[0].status.value == "UNSUPPORTED"


def test_pdf_without_pdf_extension_is_selected() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("edital.bin", ONE_PAGE_PDF))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.sources[0].status.value == "DIGITAL_TEXT"


def test_integrity_mismatch() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, ONE_PAGE_PDF, FileType.PDF)
    storage.blobs[artifact.sha256] = b"corrupted-bytes"
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    assert result.errors[0].reason is ExtractionReason.ARTIFACT_INTEGRITY_MISMATCH


def test_partial_failure_keeps_valid_pdf() -> None:
    storage = MemoryStorage()
    payload = zip_bytes(("ok.pdf", ONE_PAGE_PDF), ("bad.pdf", FAKE_PDF_HEADER))
    artifact = _put(storage, payload, FileType.ZIP)
    result = _service(storage, PypdfTextExtractor()).extract(artifact)
    statuses = {item.source.source_path: item.status.value for item in result.sources}
    assert statuses["ok.pdf"] == "DIGITAL_TEXT"
    assert statuses["bad.pdf"] == "FAILED"
    assert result.complete is False
    assert result.metrics.files_extracted == 1
    assert result.metrics.files_failed == 1


def test_idempotent_persist() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, ONE_PAGE_PDF, FileType.PDF)
    result = _service(storage, FakeExtractor((TextPage(1, "hi", 2),))).extract(artifact)
    repo = InMemoryTextRepository()
    persist = PersistTextExtraction(repo)
    first = persist.persist(result)
    second = persist.persist(result)
    assert first.extractions_created == 1
    assert second.extractions_created == 0
    assert second.sources_created == 0


def test_new_extractor_version_coexists() -> None:
    storage = MemoryStorage()
    artifact = _put(storage, ONE_PAGE_PDF, FileType.PDF)
    pages = (TextPage(1, "hi", 2),)
    first = _service(storage, FakeExtractor(pages, version="1")).extract(artifact)
    second = _service(storage, FakeExtractor(pages, version="2")).extract(artifact)
    repo = InMemoryTextRepository()
    persist = PersistTextExtraction(repo)
    persist.persist(first)
    outcome = persist.persist(second)
    assert outcome.extractions_created == 1
    assert outcome.sources_created == 0
