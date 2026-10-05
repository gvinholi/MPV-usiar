"""Catálogo documental em memória — sem HTTP."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from collector.application import (
    CatalogProcessDocuments,
    DocumentIdentityConflictError,
    DocumentQuery,
    PersistDocumentCatalog,
    RetryPolicy,
)
from collector.application.publications.errors import TransientFetchError
from collector.infra.pncp import PncpDocumentMapper
from tests.application.documents.fakes import (
    FakeDocumentFetcher,
    InMemoryDocumentCatalogRepository,
    permanent_error,
)
from tests.application.publications.fakes import recording_waiter
from tests.infra.pncp.document_fixtures import observed_document

CAPTURED = datetime(2026, 10, 4, 21, 0, tzinfo=UTC)
PROCESS_ID = uuid4()


def _query(**kwargs) -> DocumentQuery:
    return DocumentQuery(
        process_id=PROCESS_ID,
        cnpj="00394502000144",
        year=2026,
        sequential=12795,
        **kwargs,
    )


def _catalog(fetcher: FakeDocumentFetcher) -> CatalogProcessDocuments:
    _, waiter = recording_waiter()
    return CatalogProcessDocuments(
        fetcher,
        PncpDocumentMapper(),
        retry_policy=RetryPolicy(max_attempts=1),
        waiter=waiter,
        clock=lambda: CAPTURED,
    )


def test_one_document() -> None:
    result = _catalog(FakeDocumentFetcher([observed_document()])).catalog(_query())
    assert result.complete is True
    assert result.documents_found == 1
    assert result.documents[0].sequence == 1
    assert result.failure_reason is None


def test_several_documents_are_ordered() -> None:
    items = [
        observed_document(document_sequence=2, title="B.pdf"),
        observed_document(document_sequence=1, title="A.pdf"),
    ]
    result = _catalog(FakeDocumentFetcher(items)).catalog(_query())
    assert [doc.sequence for doc in result.documents] == [1, 2]
    assert result.documents_found == 2


def test_zero_documents_is_complete() -> None:
    result = _catalog(FakeDocumentFetcher([])).catalog(_query())
    assert result.complete is True
    assert result.documents_found == 0
    assert result.documents == ()


def test_fetch_failure_is_incomplete_not_empty_success() -> None:
    result = _catalog(FakeDocumentFetcher(error=permanent_error("404"))).catalog(_query())
    assert result.complete is False
    assert result.documents_found == 0
    assert result.failure_reason == "404"


def test_same_identity_recognized_again() -> None:
    catalog = _catalog(FakeDocumentFetcher([observed_document()]))
    first = catalog.catalog(_query())
    repository = InMemoryDocumentCatalogRepository()
    persist = PersistDocumentCatalog(repository, clock=lambda: CAPTURED)
    persist.persist(first)
    second_query = _query(query_id=uuid4())
    second = catalog.catalog(second_query)
    outcome = persist.persist(second)
    assert outcome.documents_created == 0
    assert outcome.observations_created == 1
    assert len(repository.documents) == 1
    assert len(repository.observations) == 2


def test_different_documents_do_not_collide() -> None:
    items = [
        observed_document(document_sequence=1, title="A.pdf"),
        observed_document(document_sequence=2, title="B.pdf"),
    ]
    result = _catalog(FakeDocumentFetcher(items)).catalog(_query())
    persist = PersistDocumentCatalog(InMemoryDocumentCatalogRepository())
    outcome = persist.persist(result)
    assert outcome.documents_created == 2
    assert result.documents[0].identity != result.documents[1].identity


def test_same_query_is_idempotent() -> None:
    result = _catalog(FakeDocumentFetcher([observed_document()])).catalog(_query())
    persist = PersistDocumentCatalog(InMemoryDocumentCatalogRepository())
    first = persist.persist(result)
    second = persist.persist(result)
    assert first.created is True
    assert second.created is False


def test_identity_conflict_rolls_back() -> None:
    catalog = _catalog(FakeDocumentFetcher([observed_document()]))
    repository = InMemoryDocumentCatalogRepository()
    persist = PersistDocumentCatalog(repository)
    persist.persist(catalog.catalog(_query()))
    other = DocumentQuery(
        process_id=uuid4(),
        cnpj="00394502000144",
        year=2026,
        sequential=12795,
    )
    with pytest.raises(DocumentIdentityConflictError):
        persist.persist(catalog.catalog(other))
    assert len(repository.documents) == 1
    assert len(repository.queries) == 1


def test_retry_only_for_transient() -> None:
    fetcher = FakeDocumentFetcher(error=TransientFetchError("timeout"))
    _, waiter = recording_waiter()
    service = CatalogProcessDocuments(
        fetcher,
        PncpDocumentMapper(),
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.1),
        waiter=waiter,
        clock=lambda: CAPTURED,
    )
    result = service.catalog(_query())
    assert fetcher.calls == 2
    assert result.complete is False
