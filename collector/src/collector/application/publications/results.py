"""Página e resultado de uma coleta paginada — não é o domínio."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PublicationPage:
    data: tuple[Mapping[str, object], ...]
    total_registros: int
    total_paginas: int
    numero_pagina: int
    paginas_restantes: int
    empty: bool


@dataclass(frozen=True)
class PublicationCollection:
    items: tuple[Mapping[str, object], ...]
    pages_processed: int
    records_received: int
    reported_total: int | None
    first_page: int
    last_page: int | None
    complete: bool
    failed_page: int | None = None
    failure_reason: str | None = None
