"""Portas da resolução operacional. Sem SQLAlchemy."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.resolution.results import OperationalResolution
from collector.domain import ScreeningStatus


class OperationalResolutionRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def get_resolution(
        self,
        process_id: UUID,
        profile_id: UUID,
        resolver_engine_version: str,
        resolution_fingerprint: str,
    ) -> OperationalResolution | None: ...

    def insert_resolution(
        self, resolution: OperationalResolution, *, created_at: datetime
    ) -> None: ...

    def list_resolutions_for_process(
        self, process_id: UUID
    ) -> tuple[OperationalResolution, ...]: ...

    def latest_resolution(
        self, process_id: UUID, profile_id: UUID | None = None
    ) -> OperationalResolution | None: ...

    def list_current_resolutions(
        self, *, state: ScreeningStatus | None = None
    ) -> tuple[OperationalResolution, ...]: ...
