"""Fixtures do cliente PNCP com MockTransport — sem rede."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

from collector.infra.pncp import PncpClient

START = date(2026, 10, 1)
END = date(2026, 10, 4)


def valid_page_payload(
    *,
    items: list[dict[str, object]] | None = None,
    total_registros: int = 1,
    total_paginas: int = 3,
    numero_pagina: int = 1,
    paginas_restantes: int = 2,
    empty: bool = False,
) -> dict[str, object]:
    if items is None:
        items = [
            {
                "numeroControlePNCP": "00000000000000-1-000001/2026",
                "objetoCompra": "Manutenção preventiva",
            }
        ]
    return {
        "data": items,
        "totalRegistros": total_registros,
        "totalPaginas": total_paginas,
        "numeroPagina": numero_pagina,
        "paginasRestantes": paginas_restantes,
        "empty": empty,
    }


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> PncpClient:
    return PncpClient(transport=httpx.MockTransport(handler), **kwargs)
