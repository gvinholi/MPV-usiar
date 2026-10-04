"""Mapeamento domínio → persistência, sem banco."""

from datetime import UTC, datetime
from decimal import Decimal

from collector.application.collection.results import CollectionIssue, ModalityOutcome
from collector.infra.database.mapping import mapping_errors_payload, snapshot_fields
from tests.application.persistence.factories import process


def test_snapshot_uses_representative_mutable_fields() -> None:
    snapshot = process(
        "123",
        description="prazo atualizado",
        estimated_value=Decimal("2500.50"),
        closes_at=datetime(2026, 10, 15, 18, 0, tzinfo=UTC),
    )
    fields = snapshot_fields(snapshot)

    assert fields["description"] == "prazo atualizado"
    assert fields["estimated_value"] == Decimal("2500.50")
    assert isinstance(fields["estimated_value"], Decimal)
    assert fields["closes_at"] == datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
    assert fields["captured_at"] == snapshot.last_captured_at
    assert "id" not in fields
    assert "source_identities" not in fields


def test_mapping_errors_are_structured() -> None:
    outcome = ModalityOutcome(
        modality_code=6,
        complete=False,
        pages_processed=1,
        records_received=2,
        processes_mapped=1,
        mapping_errors=(
            CollectionIssue(
                modality_code=6,
                message="item inválido",
                kind="mapping",
                official_id="bad",
                item_index=1,
            ),
        ),
    )

    payload = mapping_errors_payload(outcome)

    assert payload == [
        {
            "kind": "mapping",
            "message": "item inválido",
            "official_id": "bad",
            "item_index": 1,
            "failed_page": None,
        }
    ]
