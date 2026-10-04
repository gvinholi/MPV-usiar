"""Processo de contratação: identidade, estados e timestamps."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from collector.domain import Process, ScreeningStatus, Source, SourceIdentity


def _identity(source: Source = Source.PNCP, official_id: str = "pncp-oficial-1") -> SourceIdentity:
    return SourceIdentity(source=source, official_id=official_id)


def test_process_creation() -> None:
    captured_at = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    process = Process(
        id=uuid4(),
        source_identities=(_identity(),),
        organization_name="Prefeitura Exemplo",
        organization_cnpj="00.000.000/0001-91",
        description="Manutenção preventiva de equipamentos",
        modality="Pregão Eletrônico",
        published_at=datetime(2026, 9, 20, 0, 0, tzinfo=UTC),
        closes_at=datetime(2026, 10, 1, 18, 0, tzinfo=UTC),
        state="SP",
        locality="Campinas",
        estimated_value=Decimal("15000.00"),
        official_url="https://exemplo.gov.br/edital/1",
        first_captured_at=captured_at,
        last_captured_at=captured_at,
    )

    assert process.screening_status is ScreeningStatus.RAW
    assert process.decision_reason is None
    assert process.estimated_value == Decimal("15000.00")
    assert process.source_identities[0].source is Source.PNCP


def test_process_keeps_internal_and_official_identity() -> None:
    internal_id = uuid4()
    official = _identity(official_id="controle-oficial-99")
    process = Process(id=internal_id, source_identities=(official,))

    assert process.id == internal_id
    assert process.source_identities == (official,)
    assert not hasattr(process, "title")


def test_process_can_hold_identities_from_multiple_sources() -> None:
    internal_id = uuid4()
    process = Process(
        id=internal_id,
        source_identities=(
            _identity(Source.PNCP, "oficial-pncp"),
            _identity(Source.RHS, "oficial-rhs"),
        ),
    )

    sources = {identity.source for identity in process.source_identities}
    assert process.id == internal_id
    assert sources == {Source.PNCP, Source.RHS}


def test_process_requires_at_least_one_source_identity() -> None:
    with pytest.raises(ValueError, match="ao menos uma identidade"):
        Process(id=uuid4(), source_identities=())


def test_process_rejects_duplicate_source_identities() -> None:
    identity = _identity()
    with pytest.raises(ValueError, match="duplicadas"):
        Process(id=uuid4(), source_identities=(identity, identity))


def test_process_can_represent_each_screening_status() -> None:
    for status in ScreeningStatus:
        process = Process(
            id=uuid4(),
            source_identities=(_identity(),),
            screening_status=status,
            decision_reason="aguardando edital" if status is ScreeningStatus.PENDING else None,
        )
        assert process.screening_status is status


def test_process_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="published_at"):
        Process(
            id=uuid4(),
            source_identities=(_identity(),),
            published_at=datetime(2026, 9, 20, 0, 0),
        )


def test_estimated_value_must_be_decimal() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        Process(
            id=uuid4(),
            source_identities=(_identity(),),
            estimated_value=15000.0,  # type: ignore[arg-type]
        )
