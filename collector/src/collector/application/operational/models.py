"""Contratos do runner operacional de coleta e triagem inicial."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID


@dataclass(frozen=True)
class RoundObservation:
    observation_id: UUID
    process_id: UUID
    description: str | None


@dataclass(frozen=True)
class ScreeningMetrics:
    candidates: int = 0
    pending: int = 0
    discarded: int = 0

    @property
    def evaluated(self) -> int:
        return self.candidates + self.pending + self.discarded


@dataclass(frozen=True)
class OperationalRunSummary:
    round_id: UUID
    status: str
    requested_modalities: tuple[int, ...]
    completed_modalities: tuple[int, ...]
    incomplete_modalities: tuple[int, ...]
    records_collected: int
    processes_mapped: int
    unique_processes: int
    processes_created: int
    observations_created: int
    evaluations_created: int
    resolutions_created: int
    candidates: int
    pending: int
    discarded: int
    errors: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["round_id"] = str(self.round_id)
        for name in (
            "requested_modalities",
            "completed_modalities",
            "incomplete_modalities",
        ):
            payload[name] = list(payload[name])
        return payload
