"""Coleta paginada de publicações."""

from collector.application.publications.errors import (
    FetchError,
    IncompleteCollectionError,
    PermanentFetchError,
    TransientFetchError,
)
from collector.application.publications.paginator import DEFAULT_MAX_PAGES, PublicationPaginator
from collector.application.publications.ports import PublicationPageFetcher
from collector.application.publications.query import PublicationQuery
from collector.application.publications.results import PublicationCollection, PublicationPage
from collector.application.publications.retry import RetryPolicy

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
