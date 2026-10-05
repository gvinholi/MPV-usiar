"""Persiste o catálogo documental. Sem misturar com a consulta HTTP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.documents.errors import DocumentIdentityConflictError
from collector.application.documents.ports import DocumentCatalogRepository
from collector.application.documents.results import DocumentCatalogResult
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class PersistDocumentCatalogOutcome:
    query_id: UUID
    created: bool
    documents_created: int
    observations_created: int


class PersistDocumentCatalog:
    def __init__(
        self, repository: DocumentCatalogRepository, *, clock: Clock = utc_now
    ) -> None:
        self._repository = repository
        self._clock = clock

    def persist(self, result: DocumentCatalogResult) -> PersistDocumentCatalogOutcome:
        with self._repository.transaction():
            existing = self._repository.get_query(result.query_id)
            if existing is not None:
                return PersistDocumentCatalogOutcome(
                    query_id=result.query_id,
                    created=False,
                    documents_created=0,
                    observations_created=0,
                )
            now = result.queried_at or self._clock()
            self._repository.insert_query(result, created_at=now)
            documents_created = 0
            observations_created = 0
            for document in result.documents:
                found = self._repository.find_document(
                    document.identity.source.value, document.identity.official_id
                )
                if found is None:
                    self._repository.insert_document(document, seen_at=now)
                    documents_created += 1
                    document_id = document.id
                else:
                    document_id, owner_process_id = found
                    if owner_process_id != result.process_id:
                        raise DocumentIdentityConflictError(
                            "identidade documental já pertence a outro processo"
                        )
                    self._repository.touch_document(document_id, document, seen_at=now)
                if not self._repository.has_observation(result.query_id, document_id):
                    touched = document if found is None else _with_id(document, document_id)
                    self._repository.insert_observation(
                        query_id=result.query_id,
                        document=touched,
                        created_at=now,
                    )
                    observations_created += 1
            return PersistDocumentCatalogOutcome(
                query_id=result.query_id,
                created=True,
                documents_created=documents_created,
                observations_created=observations_created,
            )


def _with_id(document, document_id: UUID):
    from dataclasses import replace

    return replace(document, id=document_id)
