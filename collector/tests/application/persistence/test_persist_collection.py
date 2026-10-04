"""Serviço de persistência com repositório em memória."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from collector.application import (
    CollectionResult,
    ConsolidationResult,
    IdentityConflictError,
    IncompatibleRoundError,
    PersistCollection,
)
from collector.domain import CollectionRound, RoundMetrics, RoundStatus, Source
from tests.application.persistence.factories import (
    ENDED,
    STARTED,
    collection_result,
    group_from,
    identity,
    outcome,
    process,
)
from tests.application.persistence.fakes import InMemoryCollectionRepository


def _service(
    repository: InMemoryCollectionRepository | None = None,
) -> tuple[PersistCollection, InMemoryCollectionRepository]:
    repository = repository or InMemoryCollectionRepository()
    return PersistCollection(repository, clock=lambda: STARTED), repository


def test_first_observation_creates_process_identity_and_round() -> None:
    service, repository = _service()
    snapshot = process("123")
    result = collection_result(snapshot)

    outcome_result = service.persist(result)

    assert outcome_result.created is True
    assert outcome_result.processes_created == 1
    assert outcome_result.identities_created == 1
    assert outcome_result.observations_created == 1
    assert len(repository.rounds) == 1
    assert repository.identities[identity("123")] == snapshot.id
    assert repository.observations[0]["snapshot"] is snapshot
    assert repository.observations[0]["process_id"] == snapshot.id


def test_same_identity_new_round_appends_observation() -> None:
    service, repository = _service()
    first = process(
        "123",
        closes_at=datetime(2026, 10, 10, 18, 0, tzinfo=UTC),
        estimated_value=Decimal("10000.00"),
    )
    service.persist(collection_result(first, round_id=uuid4()))

    second = process(
        "123",
        process_id=uuid4(),
        closes_at=datetime(2026, 10, 15, 18, 0, tzinfo=UTC),
        estimated_value=Decimal("10000.00"),
        last_captured_at=datetime(2026, 10, 4, 14, 0, tzinfo=UTC),
    )
    service.persist(collection_result(second, round_id=uuid4(), ended_at=ENDED))

    assert len(repository.processes) == 1
    assert len(repository.identities) == 1
    assert len(repository.observations) == 2
    assert len(repository.rounds) == 2
    assert repository.observations[0]["process_id"] == first.id
    assert repository.observations[1]["process_id"] == first.id
    assert repository.observations[0]["snapshot"].closes_at != repository.observations[1]["snapshot"].closes_at
    assert repository.observations[1]["snapshot"].closes_at.day == 15


def test_same_result_twice_is_idempotent() -> None:
    service, repository = _service()
    result = collection_result(process("123"))

    first = service.persist(result)
    second = service.persist(result)

    assert first.created is True
    assert second.created is False
    assert len(repository.rounds) == 1
    assert len(repository.processes) == 1
    assert len(repository.identities) == 1
    assert len(repository.observations) == 1


def test_incompatible_replay_raises() -> None:
    service, _repository = _service()
    snapshot = process("123")
    result = collection_result(snapshot)
    service.persist(result)
    changed = collection_result(
        snapshot,
        round_id=result.collection_round.id,
        status=RoundStatus.PARTIAL,
    )

    with pytest.raises(IncompatibleRoundError, match="incompatível"):
        service.persist(changed)


def test_new_official_id_creates_new_process() -> None:
    service, repository = _service()
    service.persist(collection_result(process("123")))
    service.persist(collection_result(process("456")))

    assert len(repository.processes) == 2
    assert len(repository.identities) == 2


def test_additional_identity_joins_existing_process() -> None:
    service, repository = _service()
    first = process("123")
    service.persist(collection_result(first))
    later = process("123", extra_identities=(identity("XYZ", Source.RHS),))
    service.persist(collection_result(later, round_id=uuid4()))

    assert len(repository.processes) == 1
    assert repository.identities[identity("123")] == first.id
    assert repository.identities[identity("XYZ", Source.RHS)] == first.id
    assert len(repository.observations) == 2


def test_identity_conflict_rolls_back() -> None:
    service, repository = _service()
    first = process("AAA")
    second = process("BBB")
    service.persist(collection_result(first, round_id=uuid4()))
    service.persist(collection_result(second, round_id=uuid4()))

    colliding = process("AAA", extra_identities=(identity("BBB"),))
    colliding_round = uuid4()
    with pytest.raises(IdentityConflictError, match="processos persistentes distintos"):
        service.persist(collection_result(colliding, round_id=colliding_round))

    assert colliding_round not in repository.rounds
    assert len(repository.processes) == 2
    assert len(repository.identities) == 2
    assert len(repository.observations) == 2


def test_empty_success_round_persists_without_processes() -> None:
    service, repository = _service()
    result = collection_result(
        outcomes=(outcome(records_received=0, processes_mapped=0),),
        metrics=RoundMetrics(),
        raw_processes=(),
    )

    service.persist(result)

    assert len(repository.rounds) == 1
    assert repository.rounds[result.collection_round.id].status is RoundStatus.SUCCESS
    assert repository.processes == {}
    assert repository.observations == []
    assert len(repository.outcomes) == 1


def test_partial_round_keeps_status_and_metrics() -> None:
    service, repository = _service()
    snapshot = process("123")
    result = collection_result(
        snapshot,
        status=RoundStatus.PARTIAL,
        outcomes=(
            outcome(6, complete=True, records_received=1, processes_mapped=1),
            outcome(
                8,
                complete=False,
                records_received=0,
                processes_mapped=0,
                failed_page=1,
                failure_reason="timeout",
            ),
        ),
    )

    service.persist(result)

    stored = repository.rounds[result.collection_round.id]
    assert stored.status is RoundStatus.PARTIAL
    assert stored.metrics.unique_processes == 1
    assert stored.metrics.records_collected == 1
    assert [item.modality_code for _, item in repository.outcomes] == [6, 8]


def test_raw_duplicates_do_not_create_two_observations() -> None:
    service, repository = _service()
    representative = process("123")
    raw_duplicate = process("123")
    result = collection_result(
        representative,
        raw_processes=(representative, raw_duplicate),
    )

    service.persist(result)

    assert result.processes_mapped == 2
    assert result.consolidation.unique_processes == 1
    assert len(repository.observations) == 1
    assert repository.observations[0]["snapshot"] is representative


def test_two_groups_resolving_to_same_process_persist_one_observation() -> None:
    service, repository = _service()
    first = process("123", extra_identities=(identity("XYZ", Source.RHS),))
    service.persist(collection_result(first))

    later_pncp = process("123")
    later_rhs = process("XYZ", source=Source.RHS)
    groups = (group_from(later_pncp), group_from(later_rhs))
    running = CollectionRound.start(Source.PNCP, started_at=STARTED, id=uuid4())
    finished = running.finish(
        RoundStatus.SUCCESS,
        ended_at=ENDED,
        metrics=RoundMetrics(records_collected=2, unique_processes=2),
    )
    result = CollectionResult(
        collection_round=finished,
        processes=(later_pncp, later_rhs),
        modality_outcomes=(outcome(records_received=2, processes_mapped=2),),
        requested_modalities=(6,),
        completed_modalities=(6,),
        incomplete_modalities=(),
        records_received=2,
        processes_mapped=2,
        errors=(),
        consolidation=ConsolidationResult(
            observations_received=2,
            unique_processes=2,
            duplicates=0,
            groups=groups,
        ),
    )

    service.persist(result)

    assert len(repository.observations) == 2
    assert sum(1 for item in repository.observations if item["round_id"] == finished.id) == 1
    assert repository.observations[-1]["process_id"] == first.id
