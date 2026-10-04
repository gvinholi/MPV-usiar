"""Contrato da resposta externa do PNCP — não é o modelo de domínio."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PncpPublicationPage:
    """Uma página de `/v1/contratacoes/publicacao`.

    `data` preserva os objetos JSON da fonte. A conversão para
    `collector.domain.Process` não ocorre neste adaptador.
    """

    data: tuple[Mapping[str, object], ...]
    total_registros: int
    total_paginas: int
    numero_pagina: int
    paginas_restantes: int
    empty: bool
