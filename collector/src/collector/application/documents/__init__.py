"""Catálogo de documentos oficiais. Sem download e sem análise de conteúdo."""

from collector.application.documents.catalog import CatalogProcessDocuments
from collector.application.documents.errors import (
    DocumentCatalogError,
    DocumentIdentityConflictError,
    DocumentMappingError,
)
from collector.application.documents.persist import (
    PersistDocumentCatalog,
    PersistDocumentCatalogOutcome,
)
from collector.application.documents.ports import (
    DocumentCatalogRepository,
    DocumentListFetcher,
    DocumentMapper,
)
from collector.application.documents.query import DocumentQuery
from collector.application.documents.results import (
    DocumentCatalogIssue,
    DocumentCatalogResult,
)

__all__ = [
    "CatalogProcessDocuments",
    "DocumentCatalogError",
    "DocumentCatalogIssue",
    "DocumentCatalogRepository",
    "DocumentCatalogResult",
    "DocumentIdentityConflictError",
    "DocumentListFetcher",
    "DocumentMapper",
    "DocumentMappingError",
    "DocumentQuery",
    "PersistDocumentCatalog",
    "PersistDocumentCatalogOutcome",
]
