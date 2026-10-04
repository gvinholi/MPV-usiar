"""Traduz um item `data[]` do PNCP para `collector.domain.Process`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID, uuid4

from collector.domain import Process, ScreeningStatus, Source, SourceIdentity
from collector.domain.timestamps import require_aware
from collector.infra.pncp.datetimes import parse_pncp_datetime
from collector.infra.pncp.errors import (
    PncpInvalidDateError,
    PncpInvalidIdentityError,
    PncpInvalidTypeError,
    PncpMappingError,
    PncpMissingFieldError,
)
from collector.infra.pncp.money import parse_pncp_money


def map_pncp_publication(
    item: Mapping[str, object],
    *,
    captured_at: datetime,
    process_id: UUID | None = None,
) -> Process:
    try:
        require_aware(captured_at, "captured_at")
    except ValueError as exc:
        raise PncpInvalidDateError(str(exc), field="captured_at") from exc
    if not isinstance(item, Mapping):
        raise PncpInvalidTypeError("item PNCP deve ser um objeto", field="item")

    identity = _official_identity(item)
    organization = _optional_object(item, "orgaoEntidade")
    unit = _optional_object(item, "unidadeOrgao")

    try:
        return Process(
            id=process_id or uuid4(),
            source_identities=(identity,),
            organization_name=_optional_text(organization, "razaoSocial") if organization else None,
            organization_cnpj=_optional_text(organization, "cnpj") if organization else None,
            description=_optional_text(item, "objetoCompra"),
            modality=_optional_text(item, "modalidadeNome"),
            published_at=parse_pncp_datetime(item.get("dataPublicacaoPncp"), field="dataPublicacaoPncp"),
            closes_at=parse_pncp_datetime(
                item.get("dataEncerramentoProposta"), field="dataEncerramentoProposta"
            ),
            state=_optional_text(unit, "ufSigla") if unit else None,
            locality=_optional_text(unit, "municipioNome") if unit else None,
            estimated_value=parse_pncp_money(
                item.get("valorTotalEstimado"), field="valorTotalEstimado"
            ),
            official_url=None,
            first_captured_at=captured_at,
            last_captured_at=captured_at,
            screening_status=ScreeningStatus.RAW,
        )
    except PncpMappingError:
        raise
    except (TypeError, ValueError) as exc:
        raise PncpMappingError("falha ao montar o processo de domínio") from exc


def _official_identity(item: Mapping[str, object]) -> SourceIdentity:
    raw = item.get("numeroControlePNCP")
    if raw is None:
        raise PncpMissingFieldError(
            "identidade oficial PNCP ausente", field="numeroControlePNCP"
        )
    if not isinstance(raw, str):
        raise PncpInvalidTypeError(
            "identidade oficial PNCP deve ser string", field="numeroControlePNCP"
        )
    try:
        return SourceIdentity(source=Source.PNCP, official_id=raw)
    except ValueError as exc:
        raise PncpInvalidIdentityError(
            "identidade oficial PNCP inválida", field="numeroControlePNCP"
        ) from exc


def _optional_object(item: Mapping[str, object], field: str) -> Mapping[str, object] | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PncpInvalidTypeError(f"{field} deve ser um objeto", field=field)
    return value


def _optional_text(item: Mapping[str, object], field: str) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PncpInvalidTypeError(f"{field} deve ser string", field=field)
    text = value.strip()
    return text or None
