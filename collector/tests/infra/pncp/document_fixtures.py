"""Payload de documentos derivado da sondagem real. Sem payload completo no Git."""

from __future__ import annotations

from collections.abc import Mapping


def observed_document(
    *,
    cnpj: str = "00394502000144",
    year: int = 2026,
    sequential: int = 12795,
    document_sequence: int = 1,
    title: str = "Edital e Anexos PE SRP N285-2026.zip",
    document_type: str = "Edital",
    type_id: int = 2,
    url: str | None = None,
) -> dict[str, object]:
    file_url = (
        url
        or f"https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{year}/{sequential}/arquivos/{document_sequence}"
    )
    return {
        "uri": file_url,
        "url": file_url,
        "cnpj": cnpj,
        "anoCompra": year,
        "sequencialCompra": sequential,
        "statusAtivo": True,
        "dataPublicacaoPncp": "2026-10-01T06:12:06",
        "sequencialDocumento": document_sequence,
        "titulo": title,
        "tipoDocumentoNome": document_type,
        "tipoDocumentoDescricao": document_type,
        "tipoDocumentoId": type_id,
    }


def observed_list(*items: Mapping[str, object]) -> list[dict[str, object]]:
    return [dict(item) for item in items]
