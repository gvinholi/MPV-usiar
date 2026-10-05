"""Cliente HTTP de documentos de uma contratação PNCP.

Uma chamada consulta os metadados de UMA contratação. Sem download,
sem retry e sem conversão para o domínio.

Endpoint observado: GET {base}/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
Base observada: https://pncp.gov.br/api/pncp
A API de consulta (https://pncp.gov.br/api/consulta) responde 404 neste path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import httpx

from collector.infra.pncp.errors import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)

DEFAULT_DOCUMENTS_BASE_URL = "https://pncp.gov.br/api/pncp"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "usiar-collector/0.1"
_ERROR_BODY_LIMIT = 500


def _truncate(text: str) -> str:
    if len(text) <= _ERROR_BODY_LIMIT:
        return text
    return text[:_ERROR_BODY_LIMIT] + "..."


class PncpDocumentClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_DOCUMENTS_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._transport = transport

    def documents_url(self, *, cnpj: str, year: int, sequential: int) -> str:
        digits = "".join(character for character in cnpj if character.isdigit())
        if len(digits) != 14:
            raise ValueError("cnpj deve ter 14 dígitos")
        if year < 1 or sequential < 1:
            raise ValueError("year e sequential devem ser >= 1")
        return (
            f"{self._base_url}/v1/orgaos/{digits}/compras/{year}/{sequential}/arquivos"
        )

    def get_documents(
        self, *, cnpj: str, year: int, sequential: int
    ) -> tuple[Mapping[str, object], ...]:
        url = self.documents_url(cnpj=cnpj, year=year, sequential=sequential)
        response = self._request(url)
        if response.status_code != 200:
            raise PncpHttpError(
                f"PNCP retornou HTTP {response.status_code}",
                status_code=response.status_code,
                body=_truncate(response.text),
            )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PncpInvalidJsonError("resposta do PNCP não é JSON válido") from exc
        return _parse_document_list(payload)

    def _request(self, url: str) -> httpx.Response:
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self._user_agent,
                },
                transport=self._transport,
            ) as client:
                return client.get(url)
        except httpx.TimeoutException as exc:
            raise PncpTimeoutError("timeout ao consultar documentos do PNCP") from exc
        except httpx.TransportError as exc:
            raise PncpTransportError(
                "falha de transporte ao consultar documentos do PNCP"
            ) from exc


def _parse_document_list(payload: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(payload, list):
        raise PncpUnexpectedPayloadError(
            "resposta de documentos do PNCP deve ser uma lista JSON"
        )
    items: list[Mapping[str, object]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise PncpUnexpectedPayloadError(
                f"item documentos[{index}] do PNCP deve ser um objeto JSON"
            )
        items.append(item)
    return tuple(items)
