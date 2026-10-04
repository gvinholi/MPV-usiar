"""Métricas da rodada: representação inicial, sem cálculo."""

import pytest

from collector.domain import RoundMetrics


def test_metrics_start_at_zero() -> None:
    metrics = RoundMetrics()

    assert metrics.pages_expected == 0
    assert metrics.pages_processed == 0
    assert metrics.pages_with_error == 0
    assert metrics.records_collected == 0
    assert metrics.unique_processes == 0
    assert metrics.candidates == 0
    assert metrics.selected == 0
    assert metrics.pending == 0
    assert metrics.discarded == 0
    assert metrics.documents_found == 0
    assert metrics.errors == 0


def test_metrics_accept_explicit_counts() -> None:
    metrics = RoundMetrics(
        pages_expected=4,
        pages_processed=3,
        pages_with_error=1,
        records_collected=10,
        unique_processes=8,
        candidates=5,
        selected=2,
        pending=1,
        discarded=2,
        documents_found=6,
        errors=1,
    )

    assert metrics.pages_processed == 3
    assert metrics.candidates == 5


def test_metrics_reject_negative_counts() -> None:
    with pytest.raises(ValueError, match="errors"):
        RoundMetrics(errors=-1)
