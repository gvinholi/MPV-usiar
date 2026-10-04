"""Falha no meio da paginação preserva progresso e não marca completa."""

from datetime import date

import pytest

from collector.application import (
    IncompleteCollectionError,
    PublicationPaginator,
    PublicationQuery,
    RetryPolicy,
    TransientFetchError,
)

from .fakes import FakeFetcher, empty_no_content, page, recording_waiter


def _query() -> PublicationQuery:
    return PublicationQuery(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
    )


def test_partial_failure_keeps_previous_pages() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=3, total_registros=3),
            2: page(2, items=({"id": "b"},), total_paginas=3, total_registros=3),
        },
        errors={3: [TransientFetchError("timeout"), TransientFetchError("timeout")]},
    )
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.1),
        waiter=waiter,
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        paginator.collect(_query())

    result = caught.value.result
    assert result.complete is False
    assert [item["id"] for item in result.items] == ["a", "b"]
    assert result.pages_processed == 2
    assert result.records_received == 2
    assert result.reported_total == 3
    assert result.first_page == 1
    assert result.last_page == 2
    assert result.failed_page == 3
    assert result.failure_reason is not None
    assert fetcher.calls == [1, 2, 3, 3]


def test_unexpected_empty_after_remaining_pages_is_incomplete() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=3, total_registros=3),
            2: empty_no_content(2),
        }
    )
    _, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=1), waiter=waiter
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        paginator.collect(_query())

    result = caught.value.result
    assert result.complete is False
    assert [item["id"] for item in result.items] == ["a"]
    assert result.failed_page == 2
    assert fetcher.calls == [1, 2]
