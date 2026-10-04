"""Mapper PNCP → domain.Process, com fixtures mínimas do payload real."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from collector.domain import Process, ScreeningStatus, Source
from collector.infra.pncp import (
    PncpInvalidDateError,
    PncpInvalidIdentityError,
    PncpInvalidMoneyError,
    PncpInvalidTypeError,
    PncpMissingFieldError,
    map_pncp_publication,
)
from collector.infra.pncp.datetimes import PNCP_CIVIL_TIMEZONE

CAPTURED_AT = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)


def valid_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "numeroControlePNCP": "56901275000150-1-000415/2026",
        "objetoCompra": "ALIENACAO DE BEM IMOVEL",
        "modalidadeNome": "Leilão - Eletrônico",
        "dataPublicacaoPncp": "2026-10-02T11:36:44",
        "dataEncerramentoProposta": "2026-10-23T15:00:00",
        "valorTotalEstimado": 2779054.44,
        "anoCompra": 2026,
        "sequencialCompra": 415,
        "orgaoEntidade": {
            "cnpj": "56901275000150",
            "razaoSocial": "MUNICIPIO DE ARUJA",
        },
        "unidadeOrgao": {
            "ufSigla": "SP",
            "municipioNome": "Aruja",
        },
        "linkSistemaOrigem": "www.fidalgoleiloes.com.br",
    }
    item.update(overrides)
    return item


def test_maps_valid_publication() -> None:
    process_id = uuid4()
    process = map_pncp_publication(
        valid_item(), captured_at=CAPTURED_AT, process_id=process_id
    )

    assert isinstance(process, Process)
    assert process.id == process_id
    assert process.source_identities[0].source is Source.PNCP
    assert process.source_identities[0].official_id == "56901275000150-1-000415/2026"
    assert process.organization_name == "MUNICIPIO DE ARUJA"
    assert process.organization_cnpj == "56901275000150"
    assert process.description == "ALIENACAO DE BEM IMOVEL"
    assert process.modality == "Leilão - Eletrônico"
    assert process.published_at == datetime(
        2026, 10, 2, 11, 36, 44, tzinfo=PNCP_CIVIL_TIMEZONE
    )
    assert process.closes_at == datetime(
        2026, 10, 23, 15, 0, tzinfo=PNCP_CIVIL_TIMEZONE
    )
    assert process.state == "SP"
    assert process.locality == "Aruja"
    assert process.estimated_value == Decimal("2779054.44")
    assert process.official_url is None
    assert process.first_captured_at == CAPTURED_AT
    assert process.last_captured_at == CAPTURED_AT
    assert process.screening_status is ScreeningStatus.RAW


def test_official_url_is_not_api_endpoint_or_origin_or_frontend() -> None:
    process = map_pncp_publication(
        valid_item(
            linkSistemaOrigem="https://origem.exemplo/edital",
            linkProcessoEletronico="https://processo.exemplo/1",
        ),
        captured_at=CAPTURED_AT,
    )

    assert process.official_url is None
    assert process.official_url != "https://origem.exemplo/edital"
    assert process.official_url != "https://processo.exemplo/1"
    assert process.official_url != (
        "https://pncp.gov.br/api/consulta/v1/orgaos/56901275000150/compras/2026/415"
    )
    assert process.official_url != (
        "https://pncp.gov.br/app/editais/56901275000150/2026/415"
    )


def test_generates_internal_uuid_when_not_provided() -> None:
    first = map_pncp_publication(valid_item(), captured_at=CAPTURED_AT)
    second = map_pncp_publication(valid_item(), captured_at=CAPTURED_AT)
    assert isinstance(first.id, UUID)
    assert first.id != second.id


def test_optional_value_and_deadline_and_locality_absent() -> None:
    process = map_pncp_publication(
        valid_item(
            valorTotalEstimado=None,
            dataEncerramentoProposta=None,
            unidadeOrgao=None,
        ),
        captured_at=CAPTURED_AT,
    )
    assert process.estimated_value is None
    assert process.closes_at is None
    assert process.state is None
    assert process.locality is None


def test_blank_optional_strings_become_none() -> None:
    process = map_pncp_publication(
        valid_item(objetoCompra="  ", modalidadeNome=""),
        captured_at=CAPTURED_AT,
    )
    assert process.description is None
    assert process.modality is None


def test_money_integer_decimal_zero() -> None:
    assert map_pncp_publication(
        valid_item(valorTotalEstimado=100), captured_at=CAPTURED_AT
    ).estimated_value == Decimal("100")
    assert map_pncp_publication(
        valid_item(valorTotalEstimado="100.0001"), captured_at=CAPTURED_AT
    ).estimated_value == Decimal("100.0001")
    assert map_pncp_publication(
        valid_item(valorTotalEstimado=0), captured_at=CAPTURED_AT
    ).estimated_value == Decimal("0")


def test_preserves_explicit_datetime_offset() -> None:
    process = map_pncp_publication(
        valid_item(dataPublicacaoPncp="2026-10-02T11:36:44+00:00"),
        captured_at=CAPTURED_AT,
    )
    assert process.published_at == datetime(2026, 10, 2, 11, 36, 44, tzinfo=UTC)


def test_missing_identity() -> None:
    item = valid_item()
    del item["numeroControlePNCP"]
    with pytest.raises(PncpMissingFieldError, match="identidade"):
        map_pncp_publication(item, captured_at=CAPTURED_AT)


def test_empty_identity() -> None:
    with pytest.raises(PncpInvalidIdentityError):
        map_pncp_publication(valid_item(numeroControlePNCP="   "), captured_at=CAPTURED_AT)


def test_invalid_identity_type() -> None:
    with pytest.raises(PncpInvalidTypeError, match="identidade"):
        map_pncp_publication(valid_item(numeroControlePNCP=123), captured_at=CAPTURED_AT)


def test_invalid_date() -> None:
    with pytest.raises(PncpInvalidDateError, match="dataPublicacaoPncp"):
        map_pncp_publication(
            valid_item(dataPublicacaoPncp="02/10/2026"), captured_at=CAPTURED_AT
        )


def test_invalid_money() -> None:
    with pytest.raises(PncpInvalidMoneyError):
        map_pncp_publication(valid_item(valorTotalEstimado="dez"), captured_at=CAPTURED_AT)


def test_invalid_organization_structure() -> None:
    with pytest.raises(PncpInvalidTypeError, match="orgaoEntidade"):
        map_pncp_publication(valid_item(orgaoEntidade="prefeitura"), captured_at=CAPTURED_AT)


def test_naive_captured_at_is_rejected() -> None:
    with pytest.raises(PncpInvalidDateError, match="captured_at"):
        map_pncp_publication(valid_item(), captured_at=datetime(2026, 10, 4, 15, 0))


def test_does_not_copy_unused_pncp_fields_onto_process() -> None:
    process = map_pncp_publication(valid_item(), captured_at=CAPTURED_AT)
    assert not hasattr(process, "numeroControlePNCP")
    assert not hasattr(process, "objetoCompra")
    assert not hasattr(process, "orgaoEntidade")
