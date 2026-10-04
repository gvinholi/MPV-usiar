"""Erros do cliente PNCP: transporte, HTTP, JSON e estrutura."""

import httpx
import pytest

from collector.infra.pncp import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)

from .conftest import END, START, make_client, valid_page_payload


def _get(client: object) -> object:
    return client.get_publications(
        start_date=START,
        end_date=END,
        modality_code=6,
        page=1,
    )


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(PncpTimeoutError, match="timeout"):
        _get(make_client(handler))


def test_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(PncpTransportError, match="transporte"):
        _get(make_client(handler))


def test_http_4xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    with pytest.raises(PncpHttpError) as caught:
        _get(make_client(handler))
    assert caught.value.status_code == 400
    assert "bad request" in caught.value.body


def test_http_5xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with pytest.raises(PncpHttpError) as caught:
        _get(make_client(handler))
    assert caught.value.status_code == 503


def test_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="não-json", headers={"Content-Type": "application/json"}
        )

    with pytest.raises(PncpInvalidJsonError, match="JSON"):
        _get(make_client(handler))


@pytest.mark.parametrize(
    "payload",
    [
        ["lista"],
        {"totalRegistros": 0},
        {
            "data": "x",
            "totalRegistros": 0,
            "totalPaginas": 0,
            "numeroPagina": 1,
            "paginasRestantes": 0,
            "empty": True,
        },
        {**valid_page_payload(), "totalPaginas": "2"},
        {**valid_page_payload(), "empty": "false"},
        {**valid_page_payload(items=["nao-objeto"])},
    ],
)
def test_unexpected_structure(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(PncpUnexpectedPayloadError):
        _get(make_client(handler))
