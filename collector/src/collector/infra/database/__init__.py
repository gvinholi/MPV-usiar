"""Adaptador PostgreSQL da persistência da coleta."""

from collector.infra.database.config import PersistenceConfigError, database_url
from collector.infra.database.session import create_engine_from_url, create_session_factory
from collector.infra.database.acquisition_store import (
    SqlAlchemyDocumentAcquisitionRepository,
)
from collector.infra.database.document_store import SqlAlchemyDocumentCatalogRepository
from collector.infra.database.document_screening_store import (
    SqlAlchemyDocumentScreeningRepository,
)
from collector.infra.database.resolution_store import (
    SqlAlchemyOperationalResolutionRepository,
)
from collector.infra.database.screening_store import SqlAlchemyScreeningRepository
from collector.infra.database.store import SqlAlchemyCollectionRepository
from collector.infra.database.text_store import SqlAlchemyTextExtractionRepository
from collector.infra.database.human_review_store import SqlAlchemyHumanReviewRepository

__all__ = [
    "SqlAlchemyHumanReviewRepository",
    "PersistenceConfigError",
    "SqlAlchemyCollectionRepository",
    "SqlAlchemyDocumentAcquisitionRepository",
    "SqlAlchemyDocumentCatalogRepository",
    "SqlAlchemyDocumentScreeningRepository",
    "SqlAlchemyOperationalResolutionRepository",
    "SqlAlchemyScreeningRepository",
    "SqlAlchemyTextExtractionRepository",
    "create_engine_from_url",
    "create_session_factory",
    "database_url",
]
