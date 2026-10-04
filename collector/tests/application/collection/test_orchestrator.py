"""Orquestração multi-modalidade: status, ordem, métricas e continuidade."""

from datetime import UTC, date, datetime

import pytest

from collector.application import (
    CollectionOrchestrator,
    CollectionRequest,
    CollectionRequestError,
    PublicationPaginator,
    RetryPolicy,
    TransientFetchError,
)
from collector.domain import RoundStatus
from tests.application.collection.fakes import ModalityFetcher, RecordingMapper
from tests.application.publications.fakes import empty_no_content, page, recording_waiter

CAPTURED = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)


def _request(*modalities: int) -> CollectionRequest:
    return CollectionRequest(
        start_date=date(2026, 10, 2),
        end_date=date(2026, 10, 2),
        modality_codes=modalities,
    )


def _orchestrator(
    fetcher: ModalityFetcher,
    mapper: RecordingMapper | None = None,
) -> tuple[CollectionOrchestrator, RecordingMapper]:
    mapper = mapper or RecordingMapper()
    _, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=1), waiter=waiter
    )
    service = CollectionOrchestrator(paginator, mapper, clock=lambda: CAPTURED)
    return service, mapper


def test_single_modality_success() -> None:
    fetcher = ModalityFetcher(
        pages={1: {1: page(1, items=({"numeroControlePNCP": "a"},), total_paginas=1)}}
    )
    service, mapper = _orchestrator(fetcher)
    result = service.collect(_request(1))

    assert result.collection_round.status is RoundStatus.SUCCESS
    assert [process.source_identities[0].official_id for process in result.processes] == ["a"]
    assert result.completed_modalities == (1,)
    assert result.incomplete_modalities == ()
    assert result.records_received == 1
    assert result.processes_mapped == 1
    assert len(mapper.calls) == 1
    assert mapper.calls[0][1] == CAPTURED
    assert result.processes[0].first_captured_at == CAPTURED


def test_multiple_modalities_preserve_order() -> None:
    fetcher = ModalityFetcher(
        pages={
            1: {1: page(1, items=({"numeroControlePNCP": "m1"},), total_paginas=1)},
            8: {1: page(1, items=({"numeroControlePNCP": "m8a"}, {"numeroControlePNCP": "m8b"}), total_paginas=1, total_registros=2)},
        }
    )
    service, mapper = _orchestrator(fetcher)
    result = service.collect(_request(8, 1))

    assert result.collection_round.status is RoundStatus.SUCCESS
    assert [process.source_identities[0].official_id for process in result.processes] == [
        "m8a",
        "m8b",
        "m1",
    ]
    assert fetcher.calls == [(8, 1), (1, 1)]
    assert result.requested_modalities == (8, 1)
    assert all(captured == CAPTURED for _item, captured in mapper.calls)


def test_empty_modality_and_all_empty_are_success() -> None:
    fetcher = ModalityFetcher(
        pages={1: {1: empty_no_content(1)}, 3: {1: empty_no_content(1)}}
    )
    service, _mapper = _orchestrator(fetcher)
    one = service.collect(_request(1))
    both = service.collect(_request(1, 3))

    assert one.collection_round.status is RoundStatus.SUCCESS
    assert one.processes == ()
    assert both.collection_round.status is RoundStatus.SUCCESS
    assert both.records_received == 0
    assert both.collection_round.metrics.unique_processes == 0


def test_partial_when_one_modality_fails_after_success() -> None:
    fetcher = ModalityFetcher(
        pages={6: {1: page(1, items=({"numeroControlePNCP": "ok"},), total_paginas=1)}},
        errors={8: {1: [TransientFetchError("timeout")]}},
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(6, 8))

    assert result.collection_round.status is RoundStatus.PARTIAL
    assert result.completed_modalities == (6,)
    assert result.incomplete_modalities == (8,)
    assert [process.source_identities[0].official_id for process in result.processes] == ["ok"]
    assert result.errors[0].kind == "pagination"
    assert result.errors[0].modality_code == 8


def test_partial_pagination_maps_collected_items() -> None:
    fetcher = ModalityFetcher(
        pages={
            6: {
                1: page(1, items=({"numeroControlePNCP": "p1"},), total_paginas=3, total_registros=3),
                2: page(2, items=({"numeroControlePNCP": "p2"},), total_paginas=3, total_registros=3),
            }
        },
        errors={6: {3: [TransientFetchError("timeout")]}},
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(6))

    assert result.collection_round.status is RoundStatus.PARTIAL
    assert [process.source_identities[0].official_id for process in result.processes] == [
        "p1",
        "p2",
    ]
    assert result.modality_outcomes[0].pages_processed == 2
    assert result.modality_outcomes[0].failed_page == 3
    assert result.collection_round.metrics.pages_processed == 2
    assert result.collection_round.metrics.pages_with_error == 1
    assert result.collection_round.metrics.records_collected == 2
    assert result.collection_round.metrics.unique_processes == 0


def test_mapping_error_keeps_valid_items_and_is_partial() -> None:
    fetcher = ModalityFetcher(
        pages={
            6: {
                1: page(
                    1,
                    items=(
                        {"numeroControlePNCP": "good"},
                        {"numeroControlePNCP": "bad"},
                        {"numeroControlePNCP": "also-good"},
                    ),
                    total_paginas=1,
                    total_registros=3,
                )
            }
        }
    )
    service, mapper = _orchestrator(fetcher, RecordingMapper(fail_ids=frozenset({"bad"})))
    result = service.collect(_request(6))

    assert result.collection_round.status is RoundStatus.PARTIAL
    assert [process.source_identities[0].official_id for process in result.processes] == [
        "good",
        "also-good",
    ]
    assert result.errors[0].kind == "mapping"
    assert result.errors[0].official_id == "bad"
    assert result.collection_round.metrics.errors == 1
    assert result.collection_round.metrics.records_collected == 3
    assert len(mapper.calls) == 3


def test_all_modalities_fail_is_failed_not_zero_opportunities() -> None:
    fetcher = ModalityFetcher(
        errors={
            1: {1: [TransientFetchError("timeout")]},
            6: {1: [TransientFetchError("timeout")]},
        }
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(1, 6))

    assert result.collection_round.status is RoundStatus.FAILED
    assert result.processes == ()
    assert result.records_received == 0
    assert result.completed_modalities == ()
    assert result.incomplete_modalities == (1, 6)
    assert result.collection_round.metrics.unique_processes == 0


def test_first_modality_failure_does_not_stop_second() -> None:
    fetcher = ModalityFetcher(
        pages={6: {1: page(1, items=({"numeroControlePNCP": "later"},), total_paginas=1)}},
        errors={1: {1: [TransientFetchError("timeout")]}},
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(1, 6))

    assert fetcher.calls == [(1, 1), (6, 1)]
    assert result.collection_round.status is RoundStatus.PARTIAL
    assert [process.source_identities[0].official_id for process in result.processes] == ["later"]


def test_middle_modality_failure_still_runs_later_ones() -> None:
    fetcher = ModalityFetcher(
        pages={
            1: {1: page(1, items=({"numeroControlePNCP": "first"},), total_paginas=1)},
            8: {1: page(1, items=({"numeroControlePNCP": "last"},), total_paginas=1)},
        },
        errors={6: {1: [TransientFetchError("timeout")]}},
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(1, 6, 8))

    assert [code for code, _page in fetcher.calls] == [1, 6, 8]
    assert [process.source_identities[0].official_id for process in result.processes] == [
        "first",
        "last",
    ]
    assert result.incomplete_modalities == (6,)


def test_duplicate_official_ids_are_preserved() -> None:
    same = {"numeroControlePNCP": "dup-1"}
    fetcher = ModalityFetcher(
        pages={
            1: {1: page(1, items=(same,), total_paginas=1)},
            6: {1: page(1, items=(same,), total_paginas=1)},
        }
    )
    service, _mapper = _orchestrator(fetcher)
    result = service.collect(_request(1, 6))

    assert len(result.processes) == 2
    assert [process.source_identities[0].official_id for process in result.processes] == [
        "dup-1",
        "dup-1",
    ]
    assert result.processes[0].id != result.processes[1].id
    assert result.collection_round.metrics.unique_processes == 0


def test_invalid_period() -> None:
    with pytest.raises(CollectionRequestError, match="end_date"):
        CollectionRequest(
            start_date=date(2026, 10, 3),
            end_date=date(2026, 10, 2),
            modality_codes=(1,),
        )


def test_empty_modalities() -> None:
    with pytest.raises(CollectionRequestError, match="vazia"):
        CollectionRequest(
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 2),
            modality_codes=(),
        )


def test_duplicate_modalities_are_rejected() -> None:
    with pytest.raises(CollectionRequestError, match="duplicadas"):
        CollectionRequest(
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 2),
            modality_codes=(6, 8, 6),
        )


def test_invalid_modality_code() -> None:
    with pytest.raises(CollectionRequestError, match="inválido"):
        CollectionRequest(
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 2),
            modality_codes=(0,),
        )
