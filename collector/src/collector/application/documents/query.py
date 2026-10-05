"""Pedido de catálogo documental de uma contratação já conhecida."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DocumentQuery:
    process_id: UUID
    cnpj: str
    year: int
    sequential: int
    round_id: UUID | None = None
    query_id: UUID | None = None

    def __post_init__(self) -> None:
        digits = "".join(character for character in self.cnpj if character.isdigit())
        if len(digits) != 14:
            raise ValueError("cnpj deve ter 14 dígitos")
        if self.year < 1:
            raise ValueError("year deve ser >= 1")
        if self.sequential < 1:
            raise ValueError("sequential deve ser >= 1")
        object.__setattr__(self, "cnpj", digits)
