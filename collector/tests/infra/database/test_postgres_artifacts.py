"""Persistência de artefatos e aquisições contra PostgreSQL real."""

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
    PersistCollection,
    PersistDocumentAcquisition,
    PersistDocumentCatalog,
    RetryPolicy,
)
from collector.infra.acquisition import LocalArtifactStorage
from collector.infra.database import (
    SqlAlchemyDocumentAcquisitionRepository,
    SqlAlchemyDocumentCatalogRepository,
)
from collector.infra.pncp import PncpDocumentMapper
from tests.application.acquisition.fakes import FakeDownloader
from tests.application.acquisition.zip_fixtures import PDF_BYTES, zip_bytes
from tests.application.documents.fakes import FakeDocumentFetcher
from tests.application.persistence.factories import collection_result, process
from tests.application.publications.fakes import recording_waiter
from tests.infra.pncp.document_fixtures import observed_document

pytestmark = pytest.mark.postgres
CAPTURED = datetime(2026, 10, 4, 22, 0, tzinfo=UTC)


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


def _persist_process(persist_service: PersistCollection, official_id: str = "ART"):
    snapshot = process(official_id)
    persist_service.persist(collection_result(snapshot))
    return snapshot.id


def _catalog_document(document_persist: PersistDocumentCatalog, process_id, item):
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


def _acquire(document, body: bytes, tmp_path: Path):
    return AcquireDocumentArtifact(
        FakeDownloader(body),
        LocalArtifactStorage(tmp_path),
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
        clock=lambda: CAPTURED,
        new_id=uuid4,
    ).acquire(document)


def test_artifact_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {"artifacts", "document_artifacts", "artifact_archive_entries"}.issubset(names)


def test_first_acquisition(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    process_id = _persist_process(persist_service)
    document = _catalog_document(document_persist, process_id, observed_document())
    result = _acquire(document, PDF_BYTES, tmp_path)
    outcome = acquisition_persist.persist(result)
    assert outcome.artifact_created is True
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_artifacts")).scalar_one() == 1


def test_same_hash_again(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    process_id = _persist_process(persist_service)
    document = _catalog_document(document_persist, process_id, observed_document())
    first = _acquire(document, PDF_BYTES, tmp_path)
    second = _acquire(document, PDF_BYTES, tmp_path)
    acquisition_persist.persist(first)
    outcome = acquisition_persist.persist(second)
    assert outcome.artifact_created is False
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_artifacts")).scalar_one() == 2


def test_hash_change_creates_new_artifact(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    process_id = _persist_process(persist_service)
    document = _catalog_document(document_persist, process_id, observed_document())
    acquisition_persist.persist(_acquire(document, PDF_BYTES, tmp_path))
    acquisition_persist.persist(_acquire(document, b"outro-conteudo", tmp_path))
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 2
    assert db_session.execute(text("SELECT COUNT(*) FROM document_artifacts")).scalar_one() == 2


def test_two_documents_same_hash_are_not_collapsed(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    first_id = _persist_process(persist_service, "DOC-A")
    second_id = _persist_process(persist_service, "DOC-B")
    first = _catalog_document(document_persist, first_id, observed_document())
    second = _catalog_document(
        document_persist,
        second_id,
        observed_document(cnpj="00509968000148", sequential=3341),
    )
    acquisition_persist.persist(_acquire(first, PDF_BYTES, tmp_path))
    acquisition_persist.persist(_acquire(second, PDF_BYTES, tmp_path))
    assert db_session.execute(text("SELECT COUNT(*) FROM process_documents")).scalar_one() == 2
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 1
    owners = set(
        db_session.execute(text("SELECT document_id FROM document_artifacts")).scalars()
    )
    assert owners == {first.id, second.id}


def test_zip_manifest_persisted(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    process_id = _persist_process(persist_service)
    document = _catalog_document(document_persist, process_id, observed_document())
    payload = zip_bytes(("edital.pdf", PDF_BYTES), ("anexo/a.txt", b"ok"))
    acquisition_persist.persist(_acquire(document, payload, tmp_path))
    names = set(
        db_session.execute(text("SELECT original_path FROM artifact_archive_entries")).scalars()
    )
    assert names == {"edital.pdf", "anexo/a.txt"}


def test_failed_acquisition_has_no_artifact(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    db_session: Session,
    tmp_path: Path,
) -> None:
    process_id = _persist_process(persist_service)
    document = _catalog_document(document_persist, process_id, observed_document())
    result = _acquire(document, b"", tmp_path)
    acquisition_persist.persist(result)
    assert db_session.execute(text("SELECT COUNT(*) FROM artifacts")).scalar_one() == 0
    complete, reason = db_session.execute(
        text("SELECT complete, reason_code FROM document_artifacts")
    ).one()
    assert complete is False
    assert reason == "EMPTY_FILE"
