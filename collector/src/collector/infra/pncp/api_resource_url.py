"""Recurso técnico da API de consulta do PNCP.

Não é a página pública navegável da contratação. Não preenche
`Process.official_url`.
"""

from __future__ import annotations

DEFAULT_CONSULTATION_BASE_URL = "https://pncp.gov.br/api/consulta"


def build_pncp_api_resource_url(
    *,
    cnpj: str,
    year: int,
    sequential: int,
    base_url: str = DEFAULT_CONSULTATION_BASE_URL,
) -> str:
    if year < 1:
        raise ValueError("year deve ser >= 1")
    if sequential < 1:
        raise ValueError("sequential deve ser >= 1")
    digits = "".join(character for character in cnpj if character.isdigit())
    if len(digits) != 14:
        raise ValueError("cnpj deve ter 14 dígitos")
    return f"{base_url.rstrip('/')}/v1/orgaos/{digits}/compras/{year}/{sequential}"
