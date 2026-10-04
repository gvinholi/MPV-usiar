"""Reexecução da mesma rodada vs estado incompatível."""

from datetime import UTC, datetime
from uuid import uuid4

from collector.application.persistence.compatibility import rounds_compatible
from collector.domain import CollectionRound, RoundMetrics, RoundStatus, Source

STARTED = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
ENDED = datetime(2026, 10, 4, 10, 5, tzinfo=UTC)


def _round(*, status: RoundStatus = RoundStatus.SUCCESS, unique: int = 1) -> CollectionRound:
    return CollectionRound.start(
        Source.PNCP, started_at=STARTED, id=uuid4()
    ).finish(
        status,
        ended_at=ENDED,
        metrics=RoundMetrics(records_collected=unique, unique_processes=unique),
    )


def test_identical_rounds_are_compatible() -> None:
    stored = _round()
    assert rounds_compatible(stored, stored)


def test_different_status_is_incompatible() -> None:
    first = _round(status=RoundStatus.SUCCESS)
    second = CollectionRound(
        id=first.id,
        source=first.source,
        started_at=first.started_at,
        ended_at=first.ended_at,
        status=RoundStatus.PARTIAL,
        metrics=first.metrics,
    )
    assert not rounds_compatible(first, second)


def test_different_metrics_are_incompatible() -> None:
    first = _round(unique=1)
    second = CollectionRound(
        id=first.id,
        source=first.source,
        started_at=first.started_at,
        ended_at=first.ended_at,
        status=first.status,
        metrics=RoundMetrics(records_collected=2, unique_processes=2),
    )
    assert not rounds_compatible(first, second)
