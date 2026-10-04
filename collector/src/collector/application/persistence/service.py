"""Persiste CollectionResult sem misturar coleta e gravação.

Uma transação por persistência. Reexecução do mesmo resultado é
idempotente. Nova rodada com a mesma identidade cria nova observação.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.collection.results import CollectionResult
from collector.application.persistence.compatibility import rounds_compatible
from collector.application.persistence.errors import (
    IdentityConflictError,
    IncompatibleRoundError,
)
from collector.application.persistence.ports import CollectionRepository
from collector.application.persistence.resolution import (
    CreateProcess,
    IdentityConflict,
    ReuseProcess,
    resolve_identities,
)
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


@dataclass(frozen=True)
class PersistOutcome:
    round_id: UUID
    created: bool
    processes_created: int
    identities_created: int
    observations_created: int


class PersistCollection:
    def __init__(
        self,
        repository: CollectionRepository,
        *,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def persist(self, result: CollectionResult) -> PersistOutcome:
        with self._repository.transaction():
            return self._persist(result)

    def _persist(self, result: CollectionResult) -> PersistOutcome:
        collection_round = result.collection_round
        stored = self._repository.get_round(collection_round.id)
        if stored is not None:
            if not rounds_compatible(stored, collection_round):
                raise IncompatibleRoundError(
                    "rodada já persistida com estado incompatível"
                )
            return PersistOutcome(
                round_id=collection_round.id,
                created=False,
                processes_created=0,
                identities_created=0,
                observations_created=0,
            )

        now = self._clock()
        self._repository.insert_round(collection_round, created_at=now)
        for outcome in result.modality_outcomes:
            self._repository.insert_modality_outcome(
                collection_round.id, outcome, created_at=now
            )

        processes_created = 0
        identities_created = 0
        observations_created = 0
        observed_this_round: set[UUID] = set()

        for group in result.consolidation.groups:
            existing = self._repository.find_process_ids_by_identities(group.identities)
            decision = resolve_identities(group.identities, existing)
            if isinstance(decision, IdentityConflict):
                raise IdentityConflictError(
                    "identidades do grupo apontam para processos persistentes distintos",
                    process_ids=decision.process_ids,
                )
            if isinstance(decision, CreateProcess):
                process_id = group.process.id
                self._repository.insert_process(process_id, created_at=now)
                processes_created += 1
                for identity in decision.identities:
                    self._repository.insert_identity(
                        process_id, identity, created_at=now
                    )
                    identities_created += 1
            else:
                assert isinstance(decision, ReuseProcess)
                process_id = decision.process_id
                self._repository.touch_process(process_id, updated_at=now)
                for identity in decision.new_identities:
                    self._repository.insert_identity(
                        process_id, identity, created_at=now
                    )
                    identities_created += 1

            if (
                process_id in observed_this_round
                or self._repository.has_observation(collection_round.id, process_id)
            ):
                continue
            self._repository.insert_observation(
                observation_id=self._new_id(),
                process_id=process_id,
                round_id=collection_round.id,
                source=collection_round.source,
                snapshot=group.process,
                created_at=now,
            )
            observed_this_round.add(process_id)
            observations_created += 1

        return PersistOutcome(
            round_id=collection_round.id,
            created=True,
            processes_created=processes_created,
            identities_created=identities_created,
            observations_created=observations_created,
        )
