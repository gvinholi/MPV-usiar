"""Contadores de uma rodada de coleta.

Apenas representação. Cálculos e agregações ficam para commits posteriores.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RoundMetrics:
    pages_expected: int = 0
    pages_processed: int = 0
    pages_with_error: int = 0
    records_collected: int = 0
    unique_processes: int = 0
    candidates: int = 0
    selected: int = 0
    pending: int = 0
    discarded: int = 0
    documents_found: int = 0
    errors: int = 0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value < 0:
                raise ValueError(f"{name} não pode ser negativo")
