"""Proteções contra metadados inconsistentes, loop e limite técnico."""

from datetime import date

import pytest

from collector.application import (
    IncompleteCollectionError,
    PublicationPaginator,
    PublicationQuery,
    RetryPolicy,
)

from .fakes import FakeFetcher, page, recording_waiter


def _query() -> PublicationQuery:
    return PublicationQuery(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
    )


def _paginator(fetcher: FakeFetcher, max_pages: int = 200) -> PublicationPaginator:
    _, waiter = recording_waiter()
    return PublicationPaginator(
        fetcher,
        retry_policy=RetryPolicy(max_attempts=1),
        max_pages=max_pages,
        waiter=waiter,
    )


def test_returned_page_number_mismatch() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=2, total_registros=2),
            2: page(1, items=({"id": "a"},), total_paginas=2, total_registros=2),
        }
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        _paginator(fetcher).collect(_query())

    result = caught.value.result
    assert result.complete is False
    assert [item["id"] for item in result.items] == ["a"]
    assert result.failed_page == 2
    assert "difere da solicitada" in str(caught.value)


def test_impossible_remaining_metadata() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(
                1,
                items=({"id": "a"},),
                total_paginas=10,
                total_registros=10,
                paginas_restantes=0,
            )
        }
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        _paginator(fetcher).collect(_query())

    assert caught.value.result.complete is False
    assert caught.value.result.items == ()
    assert "incompatível" in str(caught.value)


def test_total_pages_cannot_shrink() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=4, total_registros=4),
            2: page(2, items=({"id": "b"},), total_paginas=2, total_registros=2),
        }
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        _paginator(fetcher).collect(_query())

    result = caught.value.result
    assert result.complete is False
    assert [item["id"] for item in result.items] == ["a"]
    assert "diminuiu" in str(caught.value)


def test_repeated_page_is_incomplete() -> None:
    first = page(1, items=({"id": "a"},), total_paginas=2, total_registros=2)
    fetcher = FakeFetcher(pages={1: first, 2: first})

    with pytest.raises(IncompleteCollectionError) as caught:
        _paginator(fetcher).collect(_query())

    assert caught.value.result.complete is False
    assert "difere da solicitada" in str(caught.value) or "repetida" in str(caught.value)


def test_max_pages_limit_marks_incomplete() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=9, total_registros=9),
            2: page(2, items=({"id": "b"},), total_paginas=9, total_registros=9),
            3: page(3, items=({"id": "c"},), total_paginas=9, total_registros=9),
        }
    )

    with pytest.raises(IncompleteCollectionError) as caught:
        _paginator(fetcher, max_pages=2).collect(_query())

    result = caught.value.result
    assert result.complete is False
    assert [item["id"] for item in result.items] == ["a", "b"]
    assert result.pages_processed == 2
    assert "limite" in str(caught.value)
    assert fetcher.calls == [1, 2]
