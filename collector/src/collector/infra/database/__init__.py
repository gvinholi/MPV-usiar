"""Adaptador PostgreSQL da persistência da coleta."""

from collector.infra.database.config import PersistenceConfigError, database_url
from collector.infra.database.session import create_engine_from_url, create_session_factory
from collector.infra.database.document_store import SqlAlchemyDocumentCatalogRepository
from collector.infra.database.screening_store import SqlAlchemyScreeningRepository
from collector.infra.database.store import SqlAlchemyCollectionRepository

__all__ = [
    "PersistenceConfigError",
    "SqlAlchemyCollectionRepository",
    "SqlAlchemyDocumentCatalogRepository",
    "SqlAlchemyScreeningRepository",
    "create_engine_from_url",
    "create_session_factory",
    "database_url",
]
