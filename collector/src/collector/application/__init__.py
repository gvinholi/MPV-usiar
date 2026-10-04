"""Aplicação: orquestração de casos de uso.

Pode depender de `collector.domain`. Não deve depender de adaptadores
concretos em `collector.infra`.
"""

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
    "DEFAULT_MAX_PAGES",
    "FetchError",
    "IncompleteCollectionError",
    "PermanentFetchError",
    "PublicationCollection",
    "PublicationPage",
    "PublicationPageFetcher",
    "PublicationPaginator",
    "PublicationQuery",
    "RetryPolicy",
    "TransientFetchError",
]
