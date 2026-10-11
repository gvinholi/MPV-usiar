"""Portas necessárias depois da persistência da coleta."""

from __future__ import annotations

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
