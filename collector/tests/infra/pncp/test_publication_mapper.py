"""Adaptador do mapper PNCP para a porta de aplicação."""

from datetime import UTC, datetime

import pytest

from collector.application import PublicationMappingError
from collector.infra.pncp import PncpPublicationMapper

CAPTURED = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)


def test_adapter_maps_valid_item() -> None:
    process = PncpPublicationMapper().map_publication(
        {
            "numeroControlePNCP": "56901275000150-1-000415/2026",
            "objetoCompra": "Item",
        },
        captured_at=CAPTURED,
    )
    assert process.source_identities[0].official_id == "56901275000150-1-000415/2026"
    assert process.first_captured_at == CAPTURED


def test_adapter_wraps_mapping_error() -> None:
    with pytest.raises(PublicationMappingError) as caught:
        PncpPublicationMapper().map_publication({}, captured_at=CAPTURED)
    assert caught.value.official_id is None
