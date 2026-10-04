"""Rodada de coleta: criação, status e distinção entre zero oportunidades e falha."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from collector.domain import CollectionRound, RoundMetrics, RoundStatus, Source


def test_round_starts_running_with_aware_timestamp() -> None:
    started_at = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    round_ = CollectionRound.start(Source.PNCP, started_at=started_at)

    assert isinstance(round_.id, UUID)
    assert round_.source is Source.PNCP
    assert round_.status is RoundStatus.RUNNING
    assert round_.started_at == started_at
    assert round_.started_at.tzinfo is not None
    assert round_.ended_at is None


def test_round_finishes_with_success() -> None:
    started_at = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    ended_at = started_at + timedelta(minutes=5)
    finished = CollectionRound.start(Source.PNCP, started_at=started_at).finish(
        RoundStatus.SUCCESS, ended_at=ended_at
    )

    assert finished.status is RoundStatus.SUCCESS
    assert finished.ended_at == ended_at
    assert finished.ended_at.tzinfo is not None


def test_round_finishes_with_partial() -> None:
    finished = CollectionRound.start(Source.PNCP).finish(RoundStatus.PARTIAL)

    assert finished.status is RoundStatus.PARTIAL
    assert finished.ended_at is not None
    assert finished.ended_at.tzinfo is not None


def test_round_finishes_with_failed() -> None:
    finished = CollectionRound.start(Source.PNCP).finish(RoundStatus.FAILED)

    assert finished.status is RoundStatus.FAILED
    assert finished.ended_at is not None


def test_success_with_zero_records_is_not_failure() -> None:
    started_at = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    ended_at = started_at + timedelta(minutes=1)
    empty_success = CollectionRound.start(Source.PNCP, started_at=started_at).finish(
        RoundStatus.SUCCESS, ended_at=ended_at
    )
    failed = CollectionRound.start(Source.PNCP, started_at=started_at).finish(
        RoundStatus.FAILED, ended_at=ended_at
    )

    assert empty_success.status is RoundStatus.SUCCESS
    assert empty_success.metrics.records_collected == 0
    assert failed.status is RoundStatus.FAILED
    assert empty_success.status is not failed.status


def test_cannot_finish_as_running() -> None:
    round_ = CollectionRound.start(Source.PNCP)

    with pytest.raises(ValueError, match="SUCCESS, PARTIAL ou FAILED"):
        round_.finish(RoundStatus.RUNNING)


def test_cannot_finish_twice() -> None:
    finished = CollectionRound.start(Source.PNCP).finish(RoundStatus.SUCCESS)

    with pytest.raises(ValueError, match="já finalizada"):
        finished.finish(RoundStatus.FAILED)


def test_naive_started_at_is_rejected() -> None:
    with pytest.raises(ValueError, match="started_at"):
        CollectionRound.start(Source.PNCP, started_at=datetime(2026, 9, 25, 10, 0))


def test_finish_keeps_explicit_metrics() -> None:
    metrics = RoundMetrics(records_collected=3, unique_processes=2, errors=1)
    finished = CollectionRound.start(Source.PNCP, metrics=metrics).finish(
        RoundStatus.PARTIAL
    )

    assert finished.metrics == metrics
