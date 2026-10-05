"""Fakes do catálogo documental — sem HTTP."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.documents.query import DocumentQuery
from collector.application.documents.results import DocumentCatalogResult
from collector.application.publications.errors import PermanentFetchError
from collector.domain import ProcurementDocument


class FakeDocumentFetcher:
    def __init__(
        self,
        items: Sequence[Mapping[str, object]] = (),
        error: BaseException | None = None,
    ) -> None:
        self.items = tuple(items)
        self.error = error
        self.calls = 0

    def fetch_documents(self, query: DocumentQuery) -> tuple[Mapping[str, object], ...]:
        del query
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.items


class InMemoryDocumentCatalogRepository:
    def __init__(self) -> None:
        self.queries: dict[UUID, DocumentCatalogResult] = {}
        self.documents: dict[tuple[str, str], ProcurementDocument] = {}
        self.observations: list[tuple[UUID, UUID]] = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def get_query(self, query_id: UUID) -> DocumentCatalogResult | None:
        return self.queries.get(query_id)

    def find_document(self, source: str, official_id: str) -> tuple[UUID, UUID] | None:
        document = self.documents.get((source, official_id))
        if document is None:
            return None
        return document.id, document.process_id

    def insert_query(self, result: DocumentCatalogResult, *, created_at: datetime) -> None:
        del created_at
        self.queries[result.query_id] = result

    def insert_document(self, document: ProcurementDocument, *, seen_at: datetime) -> None:
        del seen_at
        key = (document.identity.source.value, document.identity.official_id)
        self.documents[key] = document

    def touch_document(
        self, document_id: UUID, document: ProcurementDocument, *, seen_at: datetime
    ) -> None:
        del document_id, seen_at
        key = (document.identity.source.value, document.identity.official_id)
        self.documents[key] = document

    def has_observation(self, query_id: UUID, document_id: UUID) -> bool:
        return (query_id, document_id) in self.observations

    def insert_observation(
        self,
        *,
        query_id: UUID,
        document: ProcurementDocument,
        created_at: datetime,
    ) -> None:
        del created_at
        self.observations.append((query_id, document.id))


def permanent_error(message: str = "falha") -> PermanentFetchError:
    return PermanentFetchError(message, status_code=404)
