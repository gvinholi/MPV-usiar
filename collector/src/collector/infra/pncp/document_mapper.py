"""Traduz um item de documentos PNCP para o domínio.

Campos baseados no payload observado em
GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.documents.errors import DocumentMappingError
from collector.domain import ProcurementDocument, Source, SourceDocumentIdentity
from collector.infra.pncp.datetimes import parse_pncp_datetime
from collector.infra.pncp.document_identity import build_pncp_document_official_id
from collector.infra.pncp.errors import PncpInvalidDateError, PncpMappingError


class PncpDocumentMapper:
    def map_document(
        self,
        item: Mapping[str, object],
        *,
        process_id: UUID,
        captured_at: datetime,
    ) -> ProcurementDocument:
        del captured_at
        try:
            return _map(item, process_id=process_id)
        except PncpMappingError as exc:
            raise DocumentMappingError(str(exc), official_id=_optional_identity(item)) from exc
        except (TypeError, ValueError) as exc:
            raise DocumentMappingError(str(exc), official_id=_optional_identity(item)) from exc


def _map(item: Mapping[str, object], *, process_id: UUID) -> ProcurementDocument:
    if not isinstance(item, Mapping):
        raise DocumentMappingError("item de documento PNCP deve ser um objeto")
    cnpj = _required_text(item, "cnpj")
    year = _required_int(item, "anoCompra")
    sequential = _required_int(item, "sequencialCompra")
    document_sequence = _required_int(item, "sequencialDocumento")
    official_id = build_pncp_document_official_id(
        cnpj=cnpj,
        year=year,
        sequential=sequential,
        document_sequence=document_sequence,
    )
    try:
        published_at = parse_pncp_datetime(
            item.get("dataPublicacaoPncp"), field="dataPublicacaoPncp"
        )
    except (PncpInvalidDateError, PncpMappingError) as exc:
        raise DocumentMappingError(str(exc), official_id=official_id) from exc
    return ProcurementDocument(
        id=uuid4(),
        process_id=process_id,
        identity=SourceDocumentIdentity(source=Source.PNCP, official_id=official_id),
        title=_optional_text(item, "titulo"),
        document_type=_optional_text(item, "tipoDocumentoNome"),
        document_type_id=_optional_int(item, "tipoDocumentoId"),
        document_type_description=_optional_text(item, "tipoDocumentoDescricao"),
        url=_optional_text(item, "url"),
        published_at=published_at,
        active=_optional_bool(item, "statusAtivo"),
        sequence=document_sequence,
    )


def _required_text(item: Mapping[str, object], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DocumentMappingError(f"{field} ausente ou inválido")
    return value.strip()


def _required_int(item: Mapping[str, object], field: str) -> int:
    value = item.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DocumentMappingError(f"{field} deve ser inteiro")
    return value


def _optional_text(item: Mapping[str, object], field: str) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DocumentMappingError(f"{field} deve ser string")
    text = value.strip()
    return text or None


def _optional_int(item: Mapping[str, object], field: str) -> int | None:
    value = item.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DocumentMappingError(f"{field} deve ser inteiro")
    return value


def _optional_bool(item: Mapping[str, object], field: str) -> bool | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise DocumentMappingError(f"{field} deve ser booleano")
    return value


def _optional_identity(item: object) -> str | None:
    if not isinstance(item, Mapping):
        return None
    try:
        return build_pncp_document_official_id(
            cnpj=_required_text(item, "cnpj"),
            year=_required_int(item, "anoCompra"),
            sequential=_required_int(item, "sequencialCompra"),
            document_sequence=_required_int(item, "sequencialDocumento"),
        )
    except (DocumentMappingError, ValueError):
        return None
