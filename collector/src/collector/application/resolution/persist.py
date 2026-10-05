"""Persiste resolução sem alterar triagens históricas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from collector.application.resolution.ports import OperationalResolutionRepository
from collector.application.resolution.results import OperationalResolution
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class PersistResolutionOutcome:
    resolution_id: UUID
    created: bool


class PersistOperationalResolution:
    def __init__(
        self,
        repository: OperationalResolutionRepository,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def persist(
        self, resolution: OperationalResolution
    ) -> PersistResolutionOutcome:
        if resolution.profile_id is None:
            raise ValueError("resolução persistida exige profile_id")
        with self._repository.transaction():
            stored = self._repository.get_resolution(
                resolution.process_id,
                resolution.profile_id,
                resolution.resolver_engine_version,
                resolution.resolution_fingerprint,
            )
            if stored is not None:
                return PersistResolutionOutcome(
                    resolution_id=stored.id, created=False
                )
            self._repository.insert_resolution(
                resolution, created_at=self._clock()
            )
            return PersistResolutionOutcome(
                resolution_id=resolution.id, created=True
            )

    def persist_with_profile_id(
        self, resolution: OperationalResolution, profile_id: UUID
    ) -> PersistResolutionOutcome:
        to_save = (
            resolution
            if resolution.profile_id == profile_id
            else replace(resolution, profile_id=profile_id)
        )
        return self.persist(to_save)
