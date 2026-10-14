"""Retry apenas para falhas transitórias; testes sem sleep real."""

from datetime import date

import pytest

from collector.application import (
    IncompleteCollectionError,
    PermanentFetchError,
    PublicationPaginator,
    PublicationQuery,
    RetryPolicy,
    TransientFetchError,
)

from .fakes import FakeFetcher, page, recording_waiter


def _query() -> PublicationQuery:
    return PublicationQuery(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
    )


def _collect(fetcher: FakeFetcher, policy: RetryPolicy) -> object:
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(fetcher, retry_policy=policy, waiter=waiter)
    return paginator.collect(_query()), delays, fetcher


def test_timeout_then_success() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=({"id": "ok"},), total_paginas=1, total_registros=1)},
        errors={1: [TransientFetchError("timeout")]},
    )
    result, delays, _ = _collect(
        fetcher, RetryPolicy(max_attempts=3, initial_delay_seconds=0.5)
    )

    assert result.complete is True
    assert result.items[0]["id"] == "ok"
    assert delays == [0.5]
    assert fetcher.calls == [1, 1]


def test_retry_observer_receives_sanitizable_attempt_metadata() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=(), total_paginas=1, total_registros=0)},
        errors={
            1: [TransientFetchError("sensitive transport detail", status_code=503)]
        },
    )
    observed = []
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.25),
        waiter=waiter,
        retry_observer=lambda attempt, delay, error: observed.append(
            (attempt, delay, type(error).__name__, error.status_code)
        ),
    )

    paginator.collect(_query())

    assert observed == [(1, 0.25, "TransientFetchError", 503)]


def test_transport_then_success() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=({"id": "ok"},), total_paginas=1, total_registros=1)},
        errors={1: [TransientFetchError("conexão")]},
    )
    result, delays, _ = _collect(
        fetcher, RetryPolicy(max_attempts=2, initial_delay_seconds=0.1)
    )

    assert result.complete is True
    assert delays == [0.1]


def test_http_500_then_success() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=({"id": "ok"},), total_paginas=1, total_registros=1)},
        errors={1: [TransientFetchError("HTTP 500", status_code=500)]},
    )
    result, delays, _ = _collect(
        fetcher, RetryPolicy(max_attempts=2, initial_delay_seconds=0.2)
    )

    assert result.complete is True
    assert delays == [0.2]


def test_http_429_then_success() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=({"id": "ok"},), total_paginas=1, total_registros=1)},
        errors={1: [TransientFetchError("HTTP 429", status_code=429)]},
    )
    result, delays, _ = _collect(
        fetcher, RetryPolicy(max_attempts=2, initial_delay_seconds=1.0)
    )

    assert result.complete is True
    assert delays == [1.0]


def test_retries_exhausted() -> None:
    fetcher = FakeFetcher(
        pages={},
        errors={
            1: [
                TransientFetchError("timeout"),
                TransientFetchError("timeout"),
                TransientFetchError("timeout"),
            ]
        },
    )
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher,
        retry_policy=RetryPolicy(
            max_attempts=3, initial_delay_seconds=0.5, backoff_factor=2
        ),
        waiter=waiter,
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        paginator.collect(_query())

    assert caught.value.result.complete is False
    assert caught.value.result.failed_page == 1
    assert caught.value.result.items == ()
    assert delays == [0.5, 1.0]
    assert fetcher.calls == [1, 1, 1]


def test_http_400_is_not_retried() -> None:
    fetcher = FakeFetcher(
        errors={1: [PermanentFetchError("HTTP 400", status_code=400)]}
    )
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=3), waiter=waiter
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        paginator.collect(_query())

    assert caught.value.result.complete is False
    assert delays == []
    assert fetcher.calls == [1]


def test_invalid_json_is_not_retried() -> None:
    fetcher = FakeFetcher(errors={1: [PermanentFetchError("JSON inválido")]})
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=4), waiter=waiter
    )

    with pytest.raises(IncompleteCollectionError):
        paginator.collect(_query())

    assert delays == []
    assert fetcher.calls == [1]


def test_invalid_payload_is_not_retried() -> None:
    fetcher = FakeFetcher(errors={1: [PermanentFetchError("payload inválido")]})
    delays, waiter = recording_waiter()
    paginator = PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=4), waiter=waiter
    )

    with pytest.raises(IncompleteCollectionError):
        paginator.collect(_query())

    assert delays == []
    assert fetcher.calls == [1]
