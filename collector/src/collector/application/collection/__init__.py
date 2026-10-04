"""Orquestração de uma coleta lógica multi-modalidade."""

from collector.application.collection.errors import (
    CollectionRequestError,
    PublicationMappingError,
)
from collector.application.collection.orchestrator import CollectionOrchestrator
from collector.application.collection.ports import PublicationMapper
from collector.application.collection.request import CollectionRequest
from collector.application.collection.results import (
    CollectionIssue,
    CollectionResult,
    ModalityOutcome,
)

__all__ = [
    "CollectionIssue",
    "CollectionOrchestrator",
    "CollectionRequest",
    "CollectionRequestError",
    "CollectionResult",
    "ModalityOutcome",
    "PublicationMapper",
    "PublicationMappingError",
]
