"""Identidade documental: oficial da fonte, não título nem URL."""

from uuid import uuid4

import pytest

from collector.domain import ProcurementDocument, Source, SourceDocumentIdentity


def test_source_document_identity_requires_official_id() -> None:
    with pytest.raises(ValueError, match="id oficial"):
        SourceDocumentIdentity(source=Source.PNCP, official_id="  ")


def test_document_keeps_process_and_official_identity() -> None:
    identity = SourceDocumentIdentity(source=Source.PNCP, official_id="00394502000144/2026/12795/1")
    document = ProcurementDocument(
        id=uuid4(),
        process_id=uuid4(),
        identity=identity,
        title="Edital e Anexos PE SRP N285-2026.zip",
    )
    assert document.identity == identity
    assert document.title.endswith(".zip")
