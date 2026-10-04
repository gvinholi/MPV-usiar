"""Pedido de uma coleta lógica. Sem defaults de negócio (UF, modalidades)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from collector.application.collection.errors import CollectionRequestError


@dataclass(frozen=True)
class CollectionRequest:
    start_date: date
    end_date: date
    modality_codes: tuple[int, ...]
    uf: str | None = None
    page_size: int | None = None
    dispute_mode_code: int | None = None
    ibge_municipality_code: str | None = None
    cnpj: str | None = None
    administrative_unit_code: str | None = None
    user_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "modality_codes", tuple(self.modality_codes))
        if self.end_date < self.start_date:
            raise CollectionRequestError("end_date anterior a start_date")
        if not self.modality_codes:
            raise CollectionRequestError("lista de modalidades vazia")
        seen: list[int] = []
        for code in self.modality_codes:
            if isinstance(code, bool) or not isinstance(code, int) or code < 1:
                raise CollectionRequestError("código de modalidade inválido")
            if code in seen:
                raise CollectionRequestError("modalidades duplicadas")
            seen.append(code)
