"""Portas necessárias depois da persistência da coleta."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Protocol
from uuid import UUID

from .models import RoundObservation, ScreeningMetrics


class OperationalRunRepository(Protocol):
    def list_round_observations(
        self, round_id: UUID
    ) -> tuple[RoundObservation, ...]: ...

    def update_screening_metrics(
        self, round_id: UUID, metrics: ScreeningMetrics
    ) -> None: ...


class OperationalRunLock(Protocol):
    def acquire(self) -> AbstractContextManager[bool]: ...


class UnlockedOperationalRunLock:
    """Default used by the application in isolation; operational composition injects PostgreSQL."""

    def acquire(self) -> AbstractContextManager[bool]:
        return nullcontext(True)
