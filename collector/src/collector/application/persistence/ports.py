"""Porta de persistência da coleta. Sem SQLAlchemy e sem psycopg."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.collection.results import ModalityOutcome
from collector.domain import CollectionRound, Process, Source, SourceIdentity


class CollectionRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def get_round(self, round_id: UUID) -> CollectionRound | None: ...

    def find_process_ids_by_identities(
        self, identities: Sequence[SourceIdentity]
    ) -> dict[SourceIdentity, UUID]: ...

    def insert_round(
        self, collection_round: CollectionRound, *, created_at: datetime
    ) -> None: ...

    def insert_modality_outcome(
        self,
        round_id: UUID,
        outcome: ModalityOutcome,
        *,
        created_at: datetime,
    ) -> None: ...

    def insert_process(self, process_id: UUID, *, created_at: datetime) -> None: ...

    def touch_process(self, process_id: UUID, *, updated_at: datetime) -> None: ...

    def insert_identity(
        self,
        process_id: UUID,
        identity: SourceIdentity,
        *,
        created_at: datetime,
    ) -> None: ...

    def insert_observation(
        self,
        *,
        observation_id: UUID,
        process_id: UUID,
        round_id: UUID,
        source: Source,
        snapshot: Process,
        created_at: datetime,
    ) -> None: ...

    def has_observation(self, round_id: UUID, process_id: UUID) -> bool: ...
