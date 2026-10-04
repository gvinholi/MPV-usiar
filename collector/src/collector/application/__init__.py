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
    ConsolidatedProcess,
    ConsolidationError,
    ConsolidationResult,
    ModalityOutcome,
    ProcessConsolidator,
    PublicationMapper,
    PublicationMappingError,
)
from collector.application.persistence import (
    CollectionRepository,
    IdentityConflictError,
    IncompatibleRoundError,
    PersistCollection,
    PersistOutcome,
    PersistenceError,
    resolve_identities,
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
    "CollectionRepository",
    "CollectionResult",
    "ConsolidatedProcess",
    "ConsolidationError",
    "ConsolidationResult",
    "DEFAULT_MAX_PAGES",
    "FetchError",
    "IdentityConflictError",
    "IncompatibleRoundError",
    "IncompleteCollectionError",
    "ModalityOutcome",
    "PermanentFetchError",
    "PersistCollection",
    "PersistOutcome",
    "PersistenceError",
    "ProcessConsolidator",
    "PublicationCollection",
    "PublicationMapper",
    "PublicationMappingError",
    "PublicationPage",
    "PublicationPageFetcher",
    "PublicationPaginator",
    "PublicationQuery",
    "RetryPolicy",
    "TransientFetchError",
    "resolve_identities",
]
