"""Persistência do catálogo documental contra PostgreSQL real."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from collector.application import (
    CatalogProcessDocuments,
    DocumentIdentityConflictError,
    DocumentQuery,
    PersistCollection,
    PersistDocumentCatalog,
    RetryPolicy,
)
from collector.infra.database import SqlAlchemyDocumentCatalogRepository
from collector.infra.pncp import PncpDocumentMapper
from tests.application.documents.fakes import FakeDocumentFetcher
from tests.application.persistence.factories import collection_result, process
from tests.application.publications.fakes import recording_waiter
from tests.infra.pncp.document_fixtures import observed_document

pytestmark = pytest.mark.postgres
CAPTURED = datetime(2026, 10, 4, 21, 0, tzinfo=UTC)


@pytest.fixture
def document_persist(migrated_engine, db_session: Session) -> PersistDocumentCatalog:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentCatalog(SqlAlchemyDocumentCatalogRepository(factory))


def _persist_process(persist_service: PersistCollection, official_id: str = "123"):
    snapshot = process(official_id)
    result = persist_service.persist(collection_result(snapshot))
    return snapshot.id, result.round_id


def _catalog_result(process_id, items, query_id=None, round_id=None):
    _, waiter = recording_waiter()
    service = CatalogProcessDocuments(
        FakeDocumentFetcher(items),
        PncpDocumentMapper(),
        retry_policy=RetryPolicy(max_attempts=1),
        waiter=waiter,
        clock=lambda: CAPTURED,
        new_id=lambda: query_id or uuid4(),
    )
    return service.catalog(
        DocumentQuery(
            process_id=process_id,
            cnpj="00394502000144",
            year=2026,
            sequential=12795,
            round_id=round_id,
            query_id=query_id,
        )
    )


def test_document_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {
        "process_documents",
        "document_catalog_queries",
        "document_observations",
    }.issubset(names)


def test_first_document(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    process_id, round_id = _persist_process(persist_service)
    result = _catalog_result(process_id, [observed_document()], round_id=round_id)
    document_persist.persist(result)
    assert db_session.execute(text("SELECT COUNT(*) FROM process_documents")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_observations")).scalar_one() == 1
    official = db_session.execute(
        text("SELECT official_document_id FROM process_documents")
    ).scalar_one()
    assert official == "00394502000144/2026/12795/1"


def test_same_document_again_updates_last_seen(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    process_id, _round_id = _persist_process(persist_service)
    first = _catalog_result(process_id, [observed_document()], query_id=uuid4())
    document_persist.persist(first)
    second = _catalog_result(process_id, [observed_document()], query_id=uuid4())
    outcome = document_persist.persist(second)
    assert outcome.documents_created == 0
    assert outcome.observations_created == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM process_documents")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_observations")).scalar_one() == 2
    first_seen, last_seen = db_session.execute(
        text("SELECT first_seen_at, last_seen_at FROM process_documents")
    ).one()
    assert last_seen >= first_seen


def test_new_document(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    process_id, _round_id = _persist_process(persist_service)
    items = [
        observed_document(document_sequence=1, title="A.pdf"),
        observed_document(document_sequence=2, title="B.pdf"),
    ]
    document_persist.persist(_catalog_result(process_id, items))
    assert db_session.execute(text("SELECT COUNT(*) FROM process_documents")).scalar_one() == 2


def test_documents_of_different_processes(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    first_id, _ = _persist_process(persist_service, "AAA")
    second_id, _ = _persist_process(persist_service, "BBB")
    document_persist.persist(
        _catalog_result(first_id, [observed_document(document_sequence=1)])
    )
    document_persist.persist(
        _catalog_result(
            second_id,
            [observed_document(cnpj="00509968000148", sequential=3341, document_sequence=1)],
        )
    )
    owners = set(db_session.execute(text("SELECT process_id FROM process_documents")).scalars())
    assert owners == {first_id, second_id}


def test_zero_documents_persists_query(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    process_id, _ = _persist_process(persist_service)
    document_persist.persist(_catalog_result(process_id, []))
    assert db_session.execute(text("SELECT documents_found, complete FROM document_catalog_queries")).one() == (
        0,
        True,
    )
    assert db_session.execute(text("SELECT COUNT(*) FROM process_documents")).scalar_one() == 0


def test_same_query_does_not_duplicate(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    process_id, _ = _persist_process(persist_service)
    query_id = uuid4()
    result = _catalog_result(process_id, [observed_document()], query_id=query_id)
    document_persist.persist(result)
    document_persist.persist(result)
    assert db_session.execute(text("SELECT COUNT(*) FROM document_catalog_queries")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_observations")).scalar_one() == 1


def test_identity_conflict_rolls_back(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    db_session: Session,
) -> None:
    first_id, _ = _persist_process(persist_service, "AAA")
    second_id, _ = _persist_process(persist_service, "BBB")
    document_persist.persist(_catalog_result(first_id, [observed_document()]))
    with pytest.raises(DocumentIdentityConflictError):
        document_persist.persist(_catalog_result(second_id, [observed_document()]))
    owners = set(db_session.execute(text("SELECT process_id FROM process_documents")).scalars())
    assert owners == {first_id}
    assert db_session.execute(text("SELECT COUNT(*) FROM document_catalog_queries")).scalar_one() == 1
