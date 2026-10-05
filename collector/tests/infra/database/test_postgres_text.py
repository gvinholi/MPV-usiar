"""Persistência da extração textual contra PostgreSQL real."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from collector.application import (
    AcquireDocumentArtifact,
    CatalogProcessDocuments,
    DocumentAcquisitionPolicy,
    DocumentQuery,
    ExtractArtifactText,
    PersistCollection,
    PersistDocumentAcquisition,
    PersistDocumentCatalog,
    PersistTextExtraction,
    RetryPolicy,
)
from collector.infra.acquisition import LocalArtifactStorage
from collector.infra.database import (
    SqlAlchemyDocumentAcquisitionRepository,
    SqlAlchemyDocumentCatalogRepository,
    SqlAlchemyTextExtractionRepository,
)
from collector.infra.extraction import PypdfTextExtractor
from collector.infra.pncp import PncpDocumentMapper
from tests.application.acquisition.fakes import FakeDownloader
from tests.application.documents.fakes import FakeDocumentFetcher
from tests.application.extraction.pdf_fixtures import ONE_PAGE_PDF, TWO_PAGE_PDF, text_pdf
from tests.application.persistence.factories import collection_result, process
from tests.application.publications.fakes import recording_waiter
from tests.application.acquisition.zip_fixtures import zip_bytes
from tests.infra.pncp.document_fixtures import observed_document

pytestmark = pytest.mark.postgres
CAPTURED = datetime(2026, 10, 4, 23, 0, tzinfo=UTC)


@pytest.fixture
def document_persist(migrated_engine, db_session: Session) -> PersistDocumentCatalog:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentCatalog(SqlAlchemyDocumentCatalogRepository(factory))


@pytest.fixture
def acquisition_persist(
    migrated_engine, db_session: Session
) -> PersistDocumentAcquisition:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentAcquisition(SqlAlchemyDocumentAcquisitionRepository(factory))


@pytest.fixture
def text_persist(migrated_engine, db_session: Session) -> PersistTextExtraction:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistTextExtraction(SqlAlchemyTextExtractionRepository(factory))


def _catalog_document(document_persist, process_id, item):
    _, waiter = recording_waiter()
    result = CatalogProcessDocuments(
        FakeDocumentFetcher([item]),
        PncpDocumentMapper(),
        retry_policy=RetryPolicy(max_attempts=1),
        waiter=waiter,
        clock=lambda: CAPTURED,
        new_id=uuid4,
    ).catalog(
        DocumentQuery(
            process_id=process_id,
            cnpj=str(item["cnpj"]),
            year=int(item["anoCompra"]),
            sequential=int(item["sequencialCompra"]),
        )
    )
    document_persist.persist(result)
    return result.documents[0]


def test_text_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {
        "artifact_text_sources",
        "text_extractions",
        "text_extraction_pages",
    }.issubset(names)


def test_direct_pdf_and_pages(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot = process("PDF-1")
    persist_service.persist(collection_result(snapshot))
    document = _catalog_document(document_persist, snapshot.id, observed_document())
    storage = LocalArtifactStorage(tmp_path)
    acquired = AcquireDocumentArtifact(
        FakeDownloader(ONE_PAGE_PDF),
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
        clock=lambda: CAPTURED,
    ).acquire(document)
    acquisition_persist.persist(acquired)
    result = ExtractArtifactText(
        storage, PypdfTextExtractor(), clock=lambda: CAPTURED
    ).extract(acquired.artifact)
    text_persist.persist(result)
    assert db_session.execute(text("SELECT COUNT(*) FROM artifact_text_sources")).scalar_one() == 1
    assert db_session.execute(text("SELECT text FROM text_extraction_pages")).scalar_one().find("Hello") >= 0


def test_zip_member_and_idempotency(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot = process("ZIP-1")
    persist_service.persist(collection_result(snapshot))
    document = _catalog_document(document_persist, snapshot.id, observed_document())
    storage = LocalArtifactStorage(tmp_path)
    payload = zip_bytes(("edital.pdf", ONE_PAGE_PDF))
    acquired = AcquireDocumentArtifact(
        FakeDownloader(payload),
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
        clock=lambda: CAPTURED,
    ).acquire(document)
    acquisition_persist.persist(acquired)
    service = ExtractArtifactText(storage, PypdfTextExtractor(), clock=lambda: CAPTURED)
    first = service.extract(acquired.artifact)
    text_persist.persist(first)
    second = text_persist.persist(service.extract(acquired.artifact))
    assert second.extractions_created == 0
    assert db_session.execute(text("SELECT COUNT(*) FROM text_extractions")).scalar_one() == 1
    path = db_session.execute(text("SELECT source_path FROM artifact_text_sources")).scalar_one()
    assert path == "edital.pdf"


def test_new_extractor_version(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    tmp_path: Path,
    db_session: Session,
) -> None:
    snapshot = process("PDF-2")
    persist_service.persist(collection_result(snapshot))
    document = _catalog_document(document_persist, snapshot.id, observed_document())
    storage = LocalArtifactStorage(tmp_path)
    acquired = AcquireDocumentArtifact(
        FakeDownloader(ONE_PAGE_PDF),
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
        clock=lambda: CAPTURED,
    ).acquire(document)
    acquisition_persist.persist(acquired)
    first = ExtractArtifactText(
        storage, PypdfTextExtractor(extractor_version="1"), clock=lambda: CAPTURED
    ).extract(acquired.artifact)
    second = ExtractArtifactText(
        storage, PypdfTextExtractor(extractor_version="2"), clock=lambda: CAPTURED
    ).extract(acquired.artifact)
    text_persist.persist(first)
    text_persist.persist(second)
    assert db_session.execute(text("SELECT COUNT(*) FROM text_extractions")).scalar_one() == 2


def test_likely_scanned_and_same_name_different_artifacts(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    tmp_path: Path,
    db_session: Session,
) -> None:
    storage = LocalArtifactStorage(tmp_path)
    for official, sequential, body in (
        ("A", 1, text_pdf("")),
        ("B", 2, TWO_PAGE_PDF),
    ):
        snapshot = process(official)
        persist_service.persist(collection_result(snapshot))
        document = _catalog_document(
            document_persist,
            snapshot.id,
            observed_document(sequential=sequential, title="mesmo.pdf"),
        )
        acquired = AcquireDocumentArtifact(
            FakeDownloader(zip_bytes(("mesmo.pdf", body))),
            storage,
            policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
            clock=lambda: CAPTURED,
        ).acquire(document)
        acquisition_persist.persist(acquired)
        text_persist.persist(
            ExtractArtifactText(storage, PypdfTextExtractor(), clock=lambda: CAPTURED).extract(
                acquired.artifact
            )
        )
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 2
    assert db_session.execute(text("SELECT COUNT(*) FROM artifact_text_sources")).scalar_one() == 2
    scanned = db_session.execute(
        text("SELECT COUNT(*) FROM text_extractions WHERE likely_scanned")
    ).scalar_one()
    assert scanned == 1
