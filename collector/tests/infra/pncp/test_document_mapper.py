"""Mapper de documentos — campos observados na sondagem."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from collector.application.documents import DocumentMappingError
from collector.domain import Source
from collector.infra.pncp import PncpDocumentMapper, build_pncp_document_official_id
from tests.infra.pncp.document_fixtures import observed_document

CAPTURED = datetime(2026, 10, 4, 21, 0, tzinfo=UTC)


def test_maps_observed_fields() -> None:
    process_id = uuid4()
    document = PncpDocumentMapper().map_document(
        observed_document(), process_id=process_id, captured_at=CAPTURED
    )
    assert document.process_id == process_id
    assert document.identity.source is Source.PNCP
    assert document.identity.official_id == "00394502000144/2026/12795/1"
    assert document.title == "Edital e Anexos PE SRP N285-2026.zip"
    assert document.document_type == "Edital"
    assert document.document_type_id == 2
    assert document.url.endswith("/arquivos/1")
    assert document.published_at is not None
    assert document.published_at.tzinfo is not None
    assert document.active is True
    assert document.sequence == 1


def test_optional_nulls() -> None:
    item = observed_document()
    item["titulo"] = None
    item["url"] = None
    item["tipoDocumentoNome"] = None
    document = PncpDocumentMapper().map_document(
        item, process_id=uuid4(), captured_at=CAPTURED
    )
    assert document.title is None
    assert document.url is None
    assert document.document_type is None


def test_missing_identity_fields() -> None:
    item = observed_document()
    del item["sequencialDocumento"]
    with pytest.raises(DocumentMappingError):
        PncpDocumentMapper().map_document(item, process_id=uuid4(), captured_at=CAPTURED)


def test_official_id_is_not_title_or_url() -> None:
    official = build_pncp_document_official_id(
        cnpj="00394502000144", year=2026, sequential=12795, document_sequence=1
    )
    other = build_pncp_document_official_id(
        cnpj="00394502000144", year=2026, sequential=12795, document_sequence=2
    )
    assert official != other
    assert "Edital" not in official
    assert "http" not in official
