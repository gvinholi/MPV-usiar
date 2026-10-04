"""Aplicação: orquestração de casos de uso.

Pode depender de `collector.domain`. Não deve depender de adaptadores
concretos em `collector.infra`.
"""

from collector.application.collection import (
    CollectionIssue,
    CollectionOrchestrator,
    CollectionRequest,
    CollectionRequestError,
    CollectionResult,
    ModalityOutcome,
    PublicationMapper,
    PublicationMappingError,
)
from collector.application.publications import (
    DEFAULT_MAX_PAGES,
    FetchError,
    IncompleteCollectionError,
    PermanentFetchError,
    PublicationCollection,
    PublicationPage,
    PublicationPageFetcher,
    PublicationPaginator,
    PublicationQuery,
    RetryPolicy,
    TransientFetchError,
)

__all__ = [
    "CollectionIssue",
    "CollectionOrchestrator",
    "CollectionRequest",
    "CollectionRequestError",
    "CollectionResult",
    "DEFAULT_MAX_PAGES",
    "FetchError",
    "IncompleteCollectionError",
    "ModalityOutcome",
    "PermanentFetchError",
    "PublicationCollection",
    "PublicationMapper",
    "PublicationMappingError",
    "PublicationPage",
    "PublicationPageFetcher",
    "PublicationPaginator",
    "PublicationQuery",
    "RetryPolicy",
    "TransientFetchError",
]
