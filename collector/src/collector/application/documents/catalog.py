"""Cataloga documentos de uma contratação. Sem persistência e sem download."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.documents.errors import DocumentMappingError
from collector.application.documents.ports import DocumentListFetcher, DocumentMapper
from collector.application.documents.query import DocumentQuery
from collector.application.documents.results import (
    DocumentCatalogIssue,
    DocumentCatalogResult,
)
from collector.application.publications.errors import FetchError, IncompleteCollectionError
from collector.application.publications.retry import RetryPolicy, Waiter, default_waiter, retry_call
from collector.domain import ProcurementDocument
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


class CatalogProcessDocuments:
    def __init__(
        self,
        fetcher: DocumentListFetcher,
        mapper: DocumentMapper,
        *,
        retry_policy: RetryPolicy | None = None,
        waiter: Waiter = default_waiter,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._fetcher = fetcher
        self._mapper = mapper
        self._retry_policy = retry_policy or RetryPolicy()
        self._waiter = waiter
        self._clock = clock
        self._new_id = new_id

    def catalog(self, query: DocumentQuery) -> DocumentCatalogResult:
        queried_at = self._clock()
        query_id = query.query_id or self._new_id()
        try:
            items = retry_call(
                lambda: self._fetcher.fetch_documents(query),
                self._retry_policy,
                self._waiter,
            )
        except (FetchError, IncompleteCollectionError) as exc:
            return DocumentCatalogResult(
                query_id=query_id,
                process_id=query.process_id,
                round_id=query.round_id,
                documents=(),
                documents_found=0,
                complete=False,
                queried_at=queried_at,
                errors=(DocumentCatalogIssue(message=str(exc)),),
                failure_reason=str(exc),
            )

        documents: list[ProcurementDocument] = []
        issues: list[DocumentCatalogIssue] = []
        for index, item in enumerate(items):
            try:
                documents.append(
                    self._mapper.map_document(
                        item, process_id=query.process_id, captured_at=queried_at
                    )
                )
            except DocumentMappingError as exc:
                issues.append(
                    DocumentCatalogIssue(
                        message=str(exc),
                        official_id=exc.official_id,
                        item_index=index,
                    )
                )

        documents.sort(key=_document_sort_key)
        return DocumentCatalogResult(
            query_id=query_id,
            process_id=query.process_id,
            round_id=query.round_id,
            documents=tuple(documents),
            documents_found=len(documents),
            complete=not issues,
            queried_at=queried_at,
            errors=tuple(issues),
            failure_reason=None if not issues else "falha ao mapear um ou mais documentos",
        )


def _document_sort_key(document: ProcurementDocument) -> tuple[int, str]:
    sequence = document.sequence if document.sequence is not None else 10**9
    title = document.title or ""
    return (sequence, title)
