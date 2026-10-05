"""Cliente de documentos PNCP — contrato observado, sem rede."""

from __future__ import annotations

import httpx
import pytest

from collector.infra.pncp import PncpDocumentClient
from collector.infra.pncp.errors import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)
from tests.infra.pncp.document_fixtures import observed_document, observed_list


def _client(handler) -> PncpDocumentClient:
    return PncpDocumentClient(transport=httpx.MockTransport(handler))


def test_valid_list_uses_observed_path() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=observed_list(observed_document()))

    items = _client(handler).get_documents(
        cnpj="00394502000144", year=2026, sequential=12795
    )
    assert seen[0].url.path == "/api/pncp/v1/orgaos/00394502000144/compras/2026/12795/arquivos"
    assert seen[0].method == "GET"
    assert len(items) == 1
    assert items[0]["sequencialDocumento"] == 1
    assert items[0]["titulo"] == "Edital e Anexos PE SRP N285-2026.zip"


def test_zero_documents_is_success() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1) == ()


def test_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with pytest.raises(PncpTimeoutError):
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)


def test_transport() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(PncpTransportError):
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)


def test_http_429() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow")

    with pytest.raises(PncpHttpError) as exc:
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)
    assert exc.value.status_code == 429


def test_http_500() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="erro")

    with pytest.raises(PncpHttpError) as exc:
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)
    assert exc.value.status_code == 500


def test_http_404_permanent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Compra não encontrada."})

    with pytest.raises(PncpHttpError) as exc:
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=999999)
    assert exc.value.status_code == 404


def test_invalid_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="não-json")

    with pytest.raises(PncpInvalidJsonError):
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)


def test_unexpected_object_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"documentos": []})

    with pytest.raises(PncpUnexpectedPayloadError, match="lista JSON"):
        _client(handler).get_documents(cnpj="00394502000144", year=2026, sequential=1)
