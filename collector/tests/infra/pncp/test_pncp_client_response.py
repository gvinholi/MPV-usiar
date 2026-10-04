"""Resposta PNCP: dados e metadados de paginação, sem mapeamento de domínio."""

import httpx

from collector.domain import Process
from collector.infra.pncp import PncpPublicationPage

from .conftest import END, START, make_client, valid_page_payload


def test_valid_response_preserves_items_and_pagination() -> None:
    payload = valid_page_payload(
        items=[{"numeroControlePNCP": "abc-1", "objetoCompra": "Higienização"}],
        total_registros=12,
        total_paginas=2,
        numero_pagina=1,
        paginas_restantes=1,
        empty=False,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    page = make_client(handler).get_publications(
        start_date=START,
        end_date=END,
        modality_code=6,
        page=1,
    )

    assert isinstance(page, PncpPublicationPage)
    assert type(page) is not Process
    assert len(page.data) == 1
    assert page.data[0]["numeroControlePNCP"] == "abc-1"
    assert page.data[0]["objetoCompra"] == "Higienização"
    assert page.total_registros == 12
    assert page.total_paginas == 2
    assert page.numero_pagina == 1
    assert page.paginas_restantes == 1
    assert page.empty is False


def test_empty_200_is_valid_page() -> None:
    payload = valid_page_payload(
        items=[],
        total_registros=0,
        total_paginas=0,
        numero_pagina=1,
        paginas_restantes=0,
        empty=True,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    page = make_client(handler).get_publications(
        start_date=START,
        end_date=END,
        modality_code=6,
        page=1,
    )

    assert page.data == ()
    assert page.empty is True
    assert page.total_registros == 0
    assert not hasattr(page, "source_identities")


def test_http_204_returns_empty_page_without_json_parse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, text="{nao-json")

    page = make_client(handler).get_publications(
        start_date=START,
        end_date=END,
        modality_code=6,
        page=3,
    )

    assert isinstance(page, PncpPublicationPage)
    assert page.data == ()
    assert page.empty is True
    assert page.total_registros == 0
    assert page.total_paginas == 0
    assert page.paginas_restantes == 0
    assert page.numero_pagina == 3
