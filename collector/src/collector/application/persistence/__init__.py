"""Persistência da coleta: regras e portas, sem adaptador SQL."""

from collector.application.persistence.errors import (
    IdentityConflictError,
    IncompatibleRoundError,
    PersistenceError,
)
from collector.application.persistence.ports import CollectionRepository
from collector.application.persistence.resolution import (
    CreateProcess,
    IdentityConflict,
    ReuseProcess,
    resolve_identities,
)
from collector.application.persistence.service import PersistCollection, PersistOutcome

__all__ = [
    "CollectionRepository",
    "CreateProcess",
    "IdentityConflict",
    "IdentityConflictError",
    "IncompatibleRoundError",
    "PersistCollection",
    "PersistOutcome",
    "PersistenceError",
    "ReuseProcess",
    "resolve_identities",
]
