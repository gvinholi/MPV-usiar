"""Builder do recurso técnico da API — não é official_url do domínio."""

import pytest

from collector.infra.pncp import build_pncp_api_resource_url


def test_builds_api_resource_not_portal_page() -> None:
    url = build_pncp_api_resource_url(
        cnpj="56901275000150", year=2026, sequential=415
    )
    assert url == (
        "https://pncp.gov.br/api/consulta/v1/orgaos/56901275000150/compras/2026/415"
    )
    assert "/app/editais/" not in url


def test_strips_cnpj_punctuation() -> None:
    url = build_pncp_api_resource_url(
        cnpj="56.901.275/0001-50", year=2026, sequential=1
    )
    assert "/orgaos/56901275000150/compras/2026/1" in url


def test_rejects_incomplete_cnpj() -> None:
    with pytest.raises(ValueError, match="14"):
        build_pncp_api_resource_url(cnpj="123", year=2026, sequential=1)
