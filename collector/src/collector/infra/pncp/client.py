"""Cliente HTTP da API pública de consulta do PNCP.

Uma chamada devolve no máximo uma página. Sem retry, sem loop e sem
conversão para o domínio.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx

from collector.infra.pncp.errors import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)
from collector.infra.pncp.models import PncpPublicationPage

DEFAULT_BASE_URL = "https://pncp.gov.br/api/consulta"
PUBLICATIONS_PATH = "/v1/contratacoes/publicacao"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "usiar-collector/0.1"
_PNCP_DATE_FORMAT = "%Y%m%d"
_ERROR_BODY_LIMIT = 500
_PAGINATION_INT_FIELDS = (
    ("totalRegistros", "total_registros"),
    ("totalPaginas", "total_paginas"),
    ("numeroPagina", "numero_pagina"),
    ("paginasRestantes", "paginas_restantes"),
)


def _format_pncp_date(value: date) -> str:
    return value.strftime(_PNCP_DATE_FORMAT)


def _truncate(text: str) -> str:
    if len(text) <= _ERROR_BODY_LIMIT:
        return text
    return text[:_ERROR_BODY_LIMIT] + "..."


class PncpClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._transport = transport

    @property
    def publications_url(self) -> str:
        return f"{self._base_url}{PUBLICATIONS_PATH}"

    def get_publications(
        self,
        *,
        start_date: date,
        end_date: date,
        modality_code: int,
        page: int,
        uf: str | None = None,
        dispute_mode_code: int | None = None,
        ibge_municipality_code: str | None = None,
        cnpj: str | None = None,
        administrative_unit_code: str | None = None,
        user_id: int | None = None,
        page_size: int | None = None,
    ) -> PncpPublicationPage:
        if page < 1:
            raise ValueError("page deve ser >= 1")
        params: dict[str, str | int] = {
            "dataInicial": _format_pncp_date(start_date),
            "dataFinal": _format_pncp_date(end_date),
            "codigoModalidadeContratacao": modality_code,
            "pagina": page,
        }
        optional_params: dict[str, str | int | None] = {
            "uf": uf,
            "codigoModoDisputa": dispute_mode_code,
            "codigoMunicipioIbge": ibge_municipality_code,
            "cnpj": cnpj,
            "codigoUnidadeAdministrativa": administrative_unit_code,
            "idUsuario": user_id,
            "tamanhoPagina": page_size,
        }
        for key, value in optional_params.items():
            if value is not None:
                params[key] = value

        response = self._request(params)
        if response.status_code == 204:
            return _empty_page(page)
        if response.status_code != 200:
            raise PncpHttpError(
                f"PNCP retornou HTTP {response.status_code}",
                status_code=response.status_code,
                body=_truncate(response.text),
            )
        try:
            raw_payload = response.json()
        except json.JSONDecodeError as exc:
            raise PncpInvalidJsonError("resposta do PNCP não é JSON válido") from exc
        return _parse_publication_page(raw_payload)

    def _request(self, params: dict[str, str | int]) -> httpx.Response:
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self._user_agent,
                },
                transport=self._transport,
            ) as client:
                return client.get(self.publications_url, params=params)
        except httpx.TimeoutException as exc:
            raise PncpTimeoutError("timeout ao consultar o PNCP") from exc
        except httpx.TransportError as exc:
            raise PncpTransportError("falha de transporte ao consultar o PNCP") from exc


def _empty_page(requested_page: int) -> PncpPublicationPage:
    return PncpPublicationPage(
        data=(),
        total_registros=0,
        total_paginas=0,
        numero_pagina=requested_page,
        paginas_restantes=0,
        empty=True,
    )


def _parse_publication_page(payload: object) -> PncpPublicationPage:
    if not isinstance(payload, dict):
        raise PncpUnexpectedPayloadError("resposta do PNCP deve ser um objeto JSON")
    raw_data = payload.get("data")
    if not isinstance(raw_data, list):
        raise PncpUnexpectedPayloadError("resposta do PNCP exige o campo data como lista")

    parsed: dict[str, Any] = {}
    for source_name, target_name in _PAGINATION_INT_FIELDS:
        value = payload.get(source_name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise PncpUnexpectedPayloadError(
                f"resposta do PNCP exige {source_name} inteiro"
            )
        parsed[target_name] = value

    empty = payload.get("empty")
    if not isinstance(empty, bool):
        raise PncpUnexpectedPayloadError("resposta do PNCP exige empty booleano")

    items: list[dict[str, object]] = []
    for index, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise PncpUnexpectedPayloadError(
                f"item data[{index}] do PNCP deve ser um objeto JSON"
            )
        items.append(item)

    return PncpPublicationPage(
        data=tuple(items),
        empty=empty,
        **parsed,
    )
