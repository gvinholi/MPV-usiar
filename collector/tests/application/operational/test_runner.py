from __future__ import annotations

from dataclasses import replace

import pytest

from collector.application import (
    CollectionIssue,
    CollectionRequest,
    OperationalCollectionRunner,
    PersistCollection,
    PersistOperationalResolution,
    PersistScreening,
    RoundObservation,
    ScreeningMetrics,
    usiar_v1,
    usiar_v2,
)
from collector.application.persistence.errors import PersistenceError
from collector.domain import RoundStatus
from tests.application.persistence.factories import (
    collection_result,
    outcome,
    process,
)
from tests.application.persistence.fakes import InMemoryCollectionRepository
from tests.application.resolution.fakes import InMemoryResolutionRepository
from tests.application.screening.fakes import InMemoryScreeningRepository


class StubCollector:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def collect(self, request):
        self.requests.append(request)
        return self.result


class InMemoryOperationalRunRepository:
    def __init__(self, collections: InMemoryCollectionRepository):
        self._collections = collections
        self.updates: list[tuple[object, ScreeningMetrics]] = []

    def list_round_observations(self, round_id):
        return tuple(
            RoundObservation(
                observation_id=item["id"],
                process_id=item["process_id"],
                description=item["snapshot"].description,
            )
            for item in self._collections.observations
            if item["round_id"] == round_id
        )

    def update_screening_metrics(self, round_id, metrics):
        current = self._collections.rounds[round_id]
        self._collections.rounds[round_id] = replace(
            current,
            metrics=replace(
                current.metrics,
                candidates=metrics.candidates,
                pending=metrics.pending,
                discarded=metrics.discarded,
            ),
        )
        self.updates.append((round_id, metrics))


def _request(*modalities):
    from datetime import date

    return CollectionRequest(
        date(2026, 10, 1), date(2026, 10, 1), modalities or (6,), uf="SP"
    )


def _runner(result):
    collections = InMemoryCollectionRepository()
    screenings = InMemoryScreeningRepository()
    resolutions = InMemoryResolutionRepository()
    operational = InMemoryOperationalRunRepository(collections)
    runner = OperationalCollectionRunner(
        StubCollector(result),
        PersistCollection(collections),
        PersistScreening(screenings),
        PersistOperationalResolution(resolutions),
        operational,
    )
    return runner, collections, screenings, resolutions, operational


def test_success_screens_candidate_pending_and_discarded_and_updates_metrics():
    result = collection_result(
        process(
            "candidate",
            description="Manutenção preventiva de aparelhos de ar condicionado.",
        ),
        process(
            "pending",
            description="Manutenção e instalação de sistema de climatização.",
        ),
        process(
            "discarded",
            description="Aquisição de aparelhos de ar condicionado.",
        ),
    )
    runner, collections, screenings, resolutions, operational = _runner(result)

    summary = runner.run(_request(6), usiar_v1())

    assert summary.status == "SUCCESS"
    assert (summary.candidates, summary.pending, summary.discarded) == (1, 1, 1)
    assert summary.evaluations_created == 3
    assert summary.resolutions_created == 3
    assert len(screenings.evaluations) == 3
    assert len(resolutions.resolutions) == 3
    assert all(item.document_evaluation_id is None for item in resolutions.resolutions)
    stored = collections.rounds[summary.round_id]
    assert (
        stored.metrics.candidates,
        stored.metrics.pending,
        stored.metrics.discarded,
    ) == (
        1,
        1,
        1,
    )
    assert operational.updates[-1][1].evaluated == 3


def test_partial_round_and_multiple_modalities_are_preserved():
    result = collection_result(
        process(
            "candidate",
            description="Higienização de sistema de climatização.",
        ),
        status=RoundStatus.PARTIAL,
        outcomes=(
            outcome(6, complete=True),
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
    result = replace(
        result,
        errors=(CollectionIssue(8, "timeout", "pagination", failed_page=1),),
    )
    runner, *_ = _runner(result)

    summary = runner.run(_request(6, 8), usiar_v1())

    assert summary.status == "PARTIAL"
    assert summary.completed_modalities == (6,)
    assert summary.incomplete_modalities == (8,)
    assert summary.errors == 1
    assert summary.candidates == 1


def test_invalid_publication_is_reported_without_losing_valid_processes():
    result = collection_result(
        process(
            "valid",
            description="Manutenção preventiva de sistema de climatização.",
        ),
        status=RoundStatus.PARTIAL,
    )
    result = replace(
        result,
        errors=(
            CollectionIssue(
                6,
                "invalid publication",
                "mapping",
                item_index=2,
            ),
        ),
    )
    runner, *_ = _runner(result)

    summary = runner.run(_request(6), usiar_v1())

    assert summary.status == "PARTIAL"
    assert summary.errors == 1
    assert summary.unique_processes == 1
    assert summary.candidates == 1


def test_failed_round_is_not_reported_as_empty_success():
    result = collection_result(
        status=RoundStatus.FAILED,
        outcomes=(
            outcome(
                6,
                complete=False,
                records_received=0,
                processes_mapped=0,
                pages_processed=0,
                failed_page=1,
                failure_reason="unavailable",
            ),
        ),
        raw_processes=(),
    )
    result = replace(
        result,
        errors=(CollectionIssue(6, "unavailable", "pagination", failed_page=1),),
    )
    runner, *_ = _runner(result)

    summary = runner.run(_request(6), usiar_v1())

    assert summary.status == "FAILED"
    assert summary.records_collected == 0
    assert summary.errors == 1
    assert summary.completed_modalities == ()
    assert summary.incomplete_modalities == (6,)


def test_duplicate_publications_create_one_observation_and_evaluation():
    first = process(
        "same",
        description="Manutenção corretiva de ar condicionado.",
    )
    duplicate = process(
        "same",
        description="Manutenção corretiva de ar condicionado.",
    )
    result = collection_result(
        first,
        raw_processes=(first, duplicate),
    )
    runner, collections, screenings, resolutions, _ = _runner(result)

    summary = runner.run(_request(6), usiar_v1())

    assert summary.processes_mapped == 2
    assert summary.unique_processes == 1
    assert len(collections.observations) == 1
    assert len(screenings.evaluations) == 1
    assert len(resolutions.resolutions) == 1


def test_same_round_reexecution_is_idempotent():
    result = collection_result(
        process(
            "same",
            description="Manutenção preventiva de ar condicionado.",
        )
    )
    runner, collections, screenings, resolutions, _ = _runner(result)

    first = runner.run(_request(6), usiar_v1())
    second = runner.run(_request(6), usiar_v1())

    assert first.observations_created == 1
    assert second.observations_created == 0
    assert second.evaluations_created == 0
    assert second.resolutions_created == 0
    assert len(collections.observations) == 1
    assert len(screenings.evaluations) == 1
    assert len(resolutions.resolutions) == 1


def test_same_round_reexecution_with_usiar_v2_is_idempotent():
    result = collection_result(
        process(
            "same-v2",
            description="Manutenção preventiva de sistema HVAC.",
        )
    )
    runner, collections, screenings, resolutions, _ = _runner(result)

    first = runner.run(_request(6), usiar_v2())
    second = runner.run(_request(6), usiar_v2())

    assert first.candidates == 1
    assert second.evaluations_created == 0
    assert second.resolutions_created == 0
    assert len(collections.observations) == 1
    assert len(screenings.evaluations) == 1
    assert len(resolutions.resolutions) == 1


def test_persistence_failure_stops_before_metrics():
    class FailingPersistence:
        def persist(self, _result):
            raise PersistenceError("database unavailable")

    result = collection_result(process("one"))
    collections = InMemoryCollectionRepository()
    operational = InMemoryOperationalRunRepository(collections)
    runner = OperationalCollectionRunner(
        StubCollector(result),
        FailingPersistence(),
        PersistScreening(InMemoryScreeningRepository()),
        PersistOperationalResolution(InMemoryResolutionRepository()),
        operational,
    )

    with pytest.raises(PersistenceError):
        runner.run(_request(6), usiar_v1())

    assert operational.updates == []
