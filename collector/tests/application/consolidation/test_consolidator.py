"""Consolidação exata por SourceIdentity — sem fuzzy e sem persistência."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from collector.application.consolidation import (
    ConsolidationError,
    ProcessConsolidator,
)
from collector.domain import Process, Source, SourceIdentity


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 4, hour, minute, tzinfo=UTC)


def _identity(official_id: str, source: Source = Source.PNCP) -> SourceIdentity:
    return SourceIdentity(source=source, official_id=official_id)


def _process(
    official_id: str,
    *,
    source: Source = Source.PNCP,
    extra_identities: tuple[SourceIdentity, ...] = (),
    process_id: UUID | None = None,
    last_captured_at: datetime | None = None,
    description: str | None = None,
    estimated_value: Decimal | None = None,
    closes_at: datetime | None = None,
    organization_name: str | None = None,
    modality: str | None = None,
) -> Process:
    return Process(
        id=process_id or uuid4(),
        source_identities=(_identity(official_id, source),) + extra_identities,
        organization_name=organization_name,
        description=description,
        modality=modality,
        closes_at=closes_at,
        estimated_value=estimated_value,
        last_captured_at=last_captured_at,
        first_captured_at=last_captured_at,
    )


def test_empty_list() -> None:
    result = ProcessConsolidator().consolidate(())

    assert result.observations_received == 0
    assert result.unique_processes == 0
    assert result.duplicates == 0
    assert result.groups == ()


def test_single_process() -> None:
    observation = _process("ABC123")
    result = ProcessConsolidator().consolidate([observation])

    assert result.observations_received == 1
    assert result.unique_processes == 1
    assert result.duplicates == 0
    assert result.groups[0].process is observation
    assert result.groups[0].observations == (observation,)
    assert result.groups[0].observation_count == 1
    assert result.groups[0].identities == (_identity("ABC123"),)


def test_two_distinct_processes() -> None:
    first = _process("ABC123")
    second = _process("XYZ999")
    result = ProcessConsolidator().consolidate([first, second])

    assert result.unique_processes == 2
    assert result.duplicates == 0
    assert [group.process for group in result.groups] == [first, second]


def test_two_observations_same_identity() -> None:
    first = _process("ABC123", process_id=uuid4())
    second = _process("ABC123", process_id=uuid4())
    result = ProcessConsolidator().consolidate([first, second])

    assert result.observations_received == 2
    assert result.unique_processes == 1
    assert result.duplicates == 1
    assert result.groups[0].observations == (first, second)
    assert first.id != second.id


def test_three_observations_same_identity() -> None:
    observations = [_process("ABC123") for _ in range(3)]
    result = ProcessConsolidator().consolidate(observations)

    assert result.unique_processes == 1
    assert result.duplicates == 2
    assert result.groups[0].observations == tuple(observations)


def test_most_recent_observation_is_representative() -> None:
    older_id = uuid4()
    newer_id = uuid4()
    older = _process("ABC123", process_id=older_id, last_captured_at=_at(10))
    newer = _process("ABC123", process_id=newer_id, last_captured_at=_at(12))
    result = ProcessConsolidator().consolidate([older, newer])

    assert result.groups[0].process is newer
    assert result.groups[0].process.id == newer_id
    assert result.groups[0].observations == (older, newer)


def test_equal_timestamps_keep_earlier_input_as_representative() -> None:
    first_id = uuid4()
    second_id = uuid4()
    captured = _at(10)
    first = _process("ABC123", process_id=first_id, last_captured_at=captured)
    second = _process("ABC123", process_id=second_id, last_captured_at=captured)
    result = ProcessConsolidator().consolidate([first, second])

    assert result.groups[0].process is first
    assert result.groups[0].process.id == first_id
    assert result.groups[0].observations == (first, second)


def test_missing_timestamp_is_older_than_aware_timestamp() -> None:
    without = _process("ABC123", last_captured_at=None)
    with_time = _process("ABC123", last_captured_at=_at(9))
    result = ProcessConsolidator().consolidate([without, with_time])

    assert result.groups[0].process is with_time


def test_representative_uuid_is_preserved_not_regenerated() -> None:
    older = _process("ABC123", last_captured_at=_at(8))
    newer = _process("ABC123", last_captured_at=_at(11))
    result = ProcessConsolidator().consolidate([older, newer])

    assert result.groups[0].process.id == newer.id
    assert result.groups[0].process.id != older.id


def test_divergent_fields_remain_one_group() -> None:
    first = _process(
        "ABC123",
        description="manutenção preventiva",
        estimated_value=Decimal("1000.00"),
        closes_at=_at(17),
        last_captured_at=_at(9),
    )
    second = _process(
        "ABC123",
        description="manutenção corretiva atualizada",
        estimated_value=Decimal("2500.50"),
        closes_at=_at(18),
        last_captured_at=_at(11),
    )
    result = ProcessConsolidator().consolidate([first, second])

    group = result.groups[0]
    assert result.unique_processes == 1
    assert group.observations == (first, second)
    assert group.process is second
    assert group.process.description == "manutenção corretiva atualizada"
    assert group.process.estimated_value == Decimal("2500.50")
    assert group.process.closes_at == _at(18)
    assert first.description != second.description


def test_shared_identity_joins_processes() -> None:
    only_pncp = _process("123")
    both = _process("123", extra_identities=(_identity("XYZ", Source.RHS),))
    result = ProcessConsolidator().consolidate([only_pncp, both])

    assert result.unique_processes == 1
    assert result.groups[0].identities == (
        _identity("123"),
        _identity("XYZ", Source.RHS),
    )
    assert result.groups[0].observations == (only_pncp, both)


def test_transitive_identities_form_one_component() -> None:
    first = _process("123")
    bridge = _process("123", extra_identities=(_identity("XYZ", Source.RHS),))
    third = _process("XYZ", source=Source.RHS)
    result = ProcessConsolidator().consolidate([first, bridge, third])

    assert result.unique_processes == 1
    assert result.duplicates == 2
    assert result.groups[0].observations == (first, bridge, third)
    assert result.groups[0].identities == (
        _identity("123"),
        _identity("XYZ", Source.RHS),
    )


def test_unrelated_identities_stay_apart() -> None:
    pncp = _process("123")
    rhs = _process("XYZ", source=Source.RHS)
    result = ProcessConsolidator().consolidate([pncp, rhs])

    assert result.unique_processes == 2
    assert result.duplicates == 0
    assert [group.process for group in result.groups] == [pncp, rhs]


def test_connecting_observation_merges_previously_separate_identities() -> None:
    left = _process("AAA")
    right = _process("BBB")
    bridge = _process("AAA", extra_identities=(_identity("BBB"),))
    result = ProcessConsolidator().consolidate([left, right, bridge])

    assert result.unique_processes == 1
    assert result.groups[0].observations == (left, right, bridge)
    assert result.groups[0].identities == (_identity("AAA"), _identity("BBB"))


def test_group_order_follows_first_observation() -> None:
    first_b = _process("B")
    first_a = _process("A")
    second_b = _process("B")
    result = ProcessConsolidator().consolidate([first_b, first_a, second_b])

    assert [group.identities[0].official_id for group in result.groups] == ["B", "A"]
    assert result.groups[0].observations == (first_b, second_b)
    assert result.groups[1].observations == (first_a,)


def test_observation_order_inside_group_is_input_order() -> None:
    newest = _process("A", last_captured_at=_at(15))
    oldest = _process("A", last_captured_at=_at(8))
    middle = _process("A", last_captured_at=_at(12))
    result = ProcessConsolidator().consolidate([newest, oldest, middle])

    assert result.groups[0].observations == (newest, oldest, middle)
    assert result.groups[0].process is newest


def test_metrics_five_observations_three_groups() -> None:
    observations = [
        _process("G1"),
        _process("G1"),
        _process("G2"),
        _process("G3"),
        _process("G3"),
    ]
    result = ProcessConsolidator().consolidate(observations)

    assert result.observations_received == 5
    assert result.unique_processes == 3
    assert result.duplicates == 2


def test_does_not_merge_on_organization_description_value_or_date() -> None:
    shared_org = "Prefeitura Exemplo"
    shared_description = "manutenção preventiva"
    shared_value = Decimal("15000.00")
    shared_close = _at(18)
    first = _process(
        "AAA",
        organization_name=shared_org,
        description=shared_description,
        estimated_value=shared_value,
        closes_at=shared_close,
    )
    second = _process(
        "BBB",
        organization_name=shared_org,
        description=shared_description,
        estimated_value=shared_value,
        closes_at=shared_close,
    )
    result = ProcessConsolidator().consolidate([first, second])

    assert result.unique_processes == 2
    assert result.duplicates == 0
    assert result.groups[0].process is first
    assert result.groups[1].process is second


def test_uuid_is_not_deduplication_key() -> None:
    same_uuid = uuid4()
    first = _process("AAA", process_id=same_uuid)
    second = _process("BBB", process_id=same_uuid)
    result = ProcessConsolidator().consolidate([first, second])

    assert result.unique_processes == 2
    assert result.groups[0].process.id == same_uuid
    assert result.groups[1].process.id == same_uuid


def test_unexpected_failure_becomes_consolidation_error() -> None:
    class BrokenProcess:
        source_identities = (["identidade-invalida"],)

    consolidator = ProcessConsolidator()
    with pytest.raises(ConsolidationError, match="falha estrutural"):
        consolidator.consolidate([BrokenProcess()])  # type: ignore[list-item]
