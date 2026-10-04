"""Requisição do cliente PNCP: método, path, datas e filtros."""

from datetime import date

import httpx
import pytest

from collector.infra.pncp import DEFAULT_BASE_URL, PncpClient

from .conftest import END, START, make_client, valid_page_payload


def _ok(request_sink: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        request_sink.append(request)
        return httpx.Response(200, json=valid_page_payload())

    return handler


def _call(client: PncpClient, **overrides: object) -> None:
    kwargs: dict[str, object] = {
        "start_date": START,
        "end_date": END,
        "modality_code": 6,
        "page": 1,
    }
    kwargs.update(overrides)
    client.get_publications(**kwargs)  # type: ignore[arg-type]


def test_request_is_get_on_publications_path() -> None:
    seen: list[httpx.Request] = []
    _call(make_client(_ok(seen)))

    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/consulta/v1/contratacoes/publicacao"


def test_dates_are_formatted_as_yyyymmdd() -> None:
    seen: list[httpx.Request] = []
    _call(
        make_client(_ok(seen)),
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 4),
    )

    params = seen[0].url.params
    assert params["dataInicial"] == "20261001"
    assert params["dataFinal"] == "20261004"


def test_required_query_params() -> None:
    seen: list[httpx.Request] = []
    _call(make_client(_ok(seen)), modality_code=8, page=2)

    params = seen[0].url.params
    assert params["codigoModalidadeContratacao"] == "8"
    assert params["pagina"] == "2"
    assert "uf" not in params


def test_optional_uf_is_sent_only_when_provided() -> None:
    seen: list[httpx.Request] = []
    _call(make_client(_ok(seen)), uf="SP")

    assert seen[0].url.params["uf"] == "SP"


def test_optional_filters() -> None:
    seen: list[httpx.Request] = []
    _call(
        make_client(_ok(seen)),
        dispute_mode_code=1,
        ibge_municipality_code="3550308",
        cnpj="00000000000191",
        administrative_unit_code="123",
        user_id=3,
        page_size=10,
    )

    params = seen[0].url.params
    assert params["codigoModoDisputa"] == "1"
    assert params["codigoMunicipioIbge"] == "3550308"
    assert params["cnpj"] == "00000000000191"
    assert params["codigoUnidadeAdministrativa"] == "123"
    assert params["idUsuario"] == "3"
    assert params["tamanhoPagina"] == "10"


def test_base_url_is_configurable() -> None:
    seen: list[httpx.Request] = []
    client = make_client(_ok(seen), base_url="https://pncp.test/consulta")
    _call(client)

    assert str(seen[0].url).startswith(
        "https://pncp.test/consulta/v1/contratacoes/publicacao"
    )


def test_default_base_url_is_official() -> None:
    assert DEFAULT_BASE_URL == "https://pncp.gov.br/api/consulta"
    assert PncpClient().publications_url == (
        "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    )


def test_json_accept_and_configurable_user_agent() -> None:
    seen: list[httpx.Request] = []
    _call(make_client(_ok(seen), user_agent="usiar-collector-test/0.1"))

    headers = seen[0].headers
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == "usiar-collector-test/0.1"
    assert "authorization" not in headers


def test_does_not_loop_pages() -> None:
    seen: list[httpx.Request] = []
    _call(make_client(_ok(seen)), page=1)

    assert len(seen) == 1


def test_page_below_one_is_rejected_without_http() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(ValueError, match="page"):
        _call(make_client(_ok(seen)), page=0)
    assert seen == []
