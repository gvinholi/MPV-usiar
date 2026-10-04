"""Adaptador PNCP classifica erros sem paginar."""

from datetime import date

import httpx
import pytest

from collector.application import PermanentFetchError, PublicationQuery, TransientFetchError
from collector.infra.pncp import PncpClient, PncpPublicationFetcher

from .conftest import make_client, valid_page_payload


def _query() -> PublicationQuery:
    return PublicationQuery(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
    )


def test_fetcher_maps_one_successful_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_page_payload(total_paginas=1, paginas_restantes=0))

    page = PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)

    assert page.numero_pagina == 1
    assert page.total_paginas == 1
    assert len(page.data) == 1


def test_fetcher_maps_timeout_to_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(TransientFetchError):
        PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)


def test_fetcher_maps_500_to_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="erro")

    with pytest.raises(TransientFetchError) as caught:
        PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)
    assert caught.value.status_code == 500


def test_fetcher_maps_429_to_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate")

    with pytest.raises(TransientFetchError) as caught:
        PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)
    assert caught.value.status_code == 429


def test_fetcher_maps_400_to_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad")

    with pytest.raises(PermanentFetchError) as caught:
        PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)
    assert caught.value.status_code == 400


def test_fetcher_maps_invalid_json_to_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="não-json")

    with pytest.raises(PermanentFetchError, match="JSON"):
        PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)


def test_fetcher_does_not_loop_pages() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=valid_page_payload(total_paginas=5, paginas_restantes=4))

    PncpPublicationFetcher(make_client(handler)).fetch_page(_query(), 1)
    assert len(seen) == 1


def test_client_get_publications_still_one_page() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=valid_page_payload())

    PncpClient(transport=httpx.MockTransport(handler)).get_publications(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
        page=1,
    )
    assert len(seen) == 1
