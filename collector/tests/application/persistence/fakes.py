"""Repositório em memória para testes da persistência — sem PostgreSQL."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.collection.results import ModalityOutcome
from collector.application.persistence.errors import PersistenceError
from collector.domain import CollectionRound, Process, Source, SourceIdentity


class InMemoryCollectionRepository:
    def __init__(self) -> None:
        self.rounds: dict[UUID, CollectionRound] = {}
        self.outcomes: list[tuple[UUID, ModalityOutcome]] = []
        self.processes: dict[UUID, datetime] = {}
        self.identities: dict[SourceIdentity, UUID] = {}
        self.observations: list[dict[str, object]] = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def get_round(self, round_id: UUID) -> CollectionRound | None:
        return self.rounds.get(round_id)

    def find_process_ids_by_identities(
        self, identities: Sequence[SourceIdentity]
    ) -> dict[SourceIdentity, UUID]:
        return {
            identity: self.identities[identity]
            for identity in identities
            if identity in self.identities
        }

    def insert_round(
        self, collection_round: CollectionRound, *, created_at: datetime
    ) -> None:
        if collection_round.id in self.rounds:
            raise PersistenceError("rodada duplicada")
        self.rounds[collection_round.id] = collection_round

    def insert_modality_outcome(
        self,
        round_id: UUID,
        outcome: ModalityOutcome,
        *,
        created_at: datetime,
    ) -> None:
        self.outcomes.append((round_id, outcome))

    def insert_process(self, process_id: UUID, *, created_at: datetime) -> None:
        if process_id in self.processes:
            raise PersistenceError("processo duplicado")
        self.processes[process_id] = created_at

    def touch_process(self, process_id: UUID, *, updated_at: datetime) -> None:
        if process_id not in self.processes:
            raise PersistenceError("processo persistente não encontrado")
        self.processes[process_id] = updated_at

    def insert_identity(
        self,
        process_id: UUID,
        identity: SourceIdentity,
        *,
        created_at: datetime,
    ) -> None:
        if identity in self.identities:
            raise PersistenceError("identidade duplicada")
        self.identities[identity] = process_id

    def insert_observation(
        self,
        *,
        observation_id: UUID,
        process_id: UUID,
        round_id: UUID,
        source: Source,
        snapshot: Process,
        created_at: datetime,
    ) -> None:
        self.observations.append(
            {
                "id": observation_id,
                "process_id": process_id,
                "round_id": round_id,
                "source": source,
                "snapshot": snapshot,
                "created_at": created_at,
            }
        )

    def has_observation(self, round_id: UUID, process_id: UUID) -> bool:
        return any(
            item["round_id"] == round_id and item["process_id"] == process_id
            for item in self.observations
        )
