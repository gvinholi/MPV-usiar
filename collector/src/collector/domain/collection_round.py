"""Rodada de execução do coletor.

SUCCESS com zero registros é um desfecho válido e distinto de FAILED.
O status declara o resultado da execução; as métricas não o inferem.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from collector.domain.metrics import RoundMetrics
from collector.domain.source import Source
from collector.domain.timestamps import require_aware, utc_now


class RoundStatus(Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


_TERMINAL_STATUSES = frozenset(
    {RoundStatus.SUCCESS, RoundStatus.PARTIAL, RoundStatus.FAILED}
)


@dataclass(frozen=True)
class CollectionRound:
    id: UUID
    source: Source
    started_at: datetime
    metrics: RoundMetrics
    status: RoundStatus = RoundStatus.RUNNING
    ended_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.started_at, "started_at")
        if self.ended_at is not None:
            require_aware(self.ended_at, "ended_at")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at anterior a started_at")
        if self.status is RoundStatus.RUNNING and self.ended_at is not None:
            raise ValueError("rodada RUNNING não possui término")
        if self.status is not RoundStatus.RUNNING and self.ended_at is None:
            raise ValueError("rodada finalizada exige ended_at")

    @classmethod
    def start(
        cls,
        source: Source,
        *,
        started_at: datetime | None = None,
        id: UUID | None = None,
        metrics: RoundMetrics | None = None,
    ) -> CollectionRound:
        return cls(
            id=id or uuid4(),
            source=source,
            started_at=started_at or utc_now(),
            metrics=metrics or RoundMetrics(),
            status=RoundStatus.RUNNING,
            ended_at=None,
        )

    def finish(
        self,
        status: RoundStatus,
        *,
        ended_at: datetime | None = None,
        metrics: RoundMetrics | None = None,
    ) -> CollectionRound:
        if self.status is not RoundStatus.RUNNING:
            raise ValueError("rodada já finalizada")
        if status not in _TERMINAL_STATUSES:
            raise ValueError("finalização exige SUCCESS, PARTIAL ou FAILED")
        return replace(
            self,
            status=status,
            ended_at=ended_at or utc_now(),
            metrics=self.metrics if metrics is None else metrics,
        )
