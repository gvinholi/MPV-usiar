"""Repositório de resolução em memória."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.persistence.errors import PersistenceError
from collector.application.resolution.results import OperationalResolution
from collector.domain import ScreeningStatus


class InMemoryResolutionRepository:
    def __init__(self) -> None:
        self.resolutions: list[OperationalResolution] = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def get_resolution(
        self,
        process_id: UUID,
        profile_id: UUID,
        resolver_engine_version: str,
        resolution_fingerprint: str,
    ) -> OperationalResolution | None:
        for item in self.resolutions:
            if (
                item.process_id == process_id
                and item.profile_id == profile_id
                and item.resolver_engine_version == resolver_engine_version
                and item.resolution_fingerprint == resolution_fingerprint
            ):
                return item
        return None

    def insert_resolution(
        self, resolution: OperationalResolution, *, created_at: datetime
    ) -> None:
        if resolution.profile_id is None:
            raise PersistenceError("resolução persistida exige profile_id")
        self.resolutions.append(resolution)

    def list_resolutions_for_process(
        self, process_id: UUID
    ) -> tuple[OperationalResolution, ...]:
        items = [item for item in self.resolutions if item.process_id == process_id]
        return tuple(
            sorted(items, key=lambda item: (item.resolved_at, item.resolution_fingerprint), reverse=True)
        )

    def latest_resolution(
        self, process_id: UUID, profile_id: UUID | None = None
    ) -> OperationalResolution | None:
        items = [
            item
            for item in self.resolutions
            if item.process_id == process_id
            and (profile_id is None or item.profile_id == profile_id)
        ]
        if not items:
            return None
        return max(items, key=lambda item: (item.resolved_at, item.resolution_fingerprint))

    def list_current_resolutions(
        self, *, state: ScreeningStatus | None = None
    ) -> tuple[OperationalResolution, ...]:
        latest: dict[UUID, OperationalResolution] = {}
        for item in self.resolutions:
            current = latest.get(item.process_id)
            if current is None or (item.resolved_at, item.resolution_fingerprint) > (
                current.resolved_at,
                current.resolution_fingerprint,
            ):
                latest[item.process_id] = item
        values = tuple(latest.values())
        if state is None:
            return values
        return tuple(item for item in values if item.state is state)
