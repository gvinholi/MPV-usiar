"""Parâmetros de uma consulta de publicações. Sem defaults de negócio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PublicationQuery:
    start_date: date
    end_date: date
    modality_code: int
    uf: str | None = None
    dispute_mode_code: int | None = None
    ibge_municipality_code: str | None = None
    cnpj: str | None = None
    administrative_unit_code: str | None = None
    user_id: int | None = None
    page_size: int | None = None

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date anterior a start_date")
