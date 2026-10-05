"""Portas do catálogo documental. Sem httpx e sem SQLAlchemy."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.documents.query import DocumentQuery
from collector.application.documents.results import DocumentCatalogResult
from collector.domain import ProcurementDocument


class DocumentListFetcher(Protocol):
    def fetch_documents(self, query: DocumentQuery) -> tuple[Mapping[str, object], ...]: ...


class DocumentMapper(Protocol):
    def map_document(
        self,
        item: Mapping[str, object],
        *,
        process_id: UUID,
        captured_at: datetime,
    ) -> ProcurementDocument: ...


class DocumentCatalogRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def get_query(self, query_id: UUID) -> DocumentCatalogResult | None: ...

    def find_document(
        self, source: str, official_id: str
    ) -> tuple[UUID, UUID] | None: ...

    def insert_query(self, result: DocumentCatalogResult, *, created_at: datetime) -> None: ...

    def insert_document(
        self, document: ProcurementDocument, *, seen_at: datetime
    ) -> None: ...

    def touch_document(
        self, document_id: UUID, document: ProcurementDocument, *, seen_at: datetime
    ) -> None: ...

    def has_observation(self, query_id: UUID, document_id: UUID) -> bool: ...

    def insert_observation(
        self,
        *,
        query_id: UUID,
        document: ProcurementDocument,
        created_at: datetime,
    ) -> None: ...
