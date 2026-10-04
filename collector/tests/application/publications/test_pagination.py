"""Paginação sequencial: uma página, várias páginas e 204 inicial."""

from datetime import date

import pytest

from collector.application import PublicationPaginator, PublicationQuery, RetryPolicy

from .fakes import FakeFetcher, empty_no_content, page, recording_waiter


def _query() -> PublicationQuery:
    return PublicationQuery(
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        modality_code=6,
    )


def _paginator(fetcher: FakeFetcher) -> PublicationPaginator:
    _, waiter = recording_waiter()
    return PublicationPaginator(
        fetcher, retry_policy=RetryPolicy(max_attempts=1), waiter=waiter
    )


def test_single_page() -> None:
    fetcher = FakeFetcher(
        pages={1: page(1, items=({"id": "a"},), total_paginas=1, total_registros=1)}
    )
    result = _paginator(fetcher).collect(_query())

    assert fetcher.calls == [1]
    assert result.complete is True
    assert [item["id"] for item in result.items] == ["a"]
    assert result.pages_processed == 1
    assert result.records_received == 1
    assert result.reported_total == 1
    assert result.first_page == 1
    assert result.last_page == 1


def test_multiple_pages_preserve_order() -> None:
    fetcher = FakeFetcher(
        pages={
            1: page(1, items=({"id": "a"},), total_paginas=3, total_registros=3),
            2: page(2, items=({"id": "b"},), total_paginas=3, total_registros=3),
            3: page(3, items=({"id": "c"},), total_paginas=3, total_registros=3),
        }
    )
    result = _paginator(fetcher).collect(_query())

    assert fetcher.calls == [1, 2, 3]
    assert result.complete is True
    assert [item["id"] for item in result.items] == ["a", "b", "c"]
    assert result.pages_processed == 3
    assert result.records_received == 3
    assert result.reported_total == 3
    assert result.first_page == 1
    assert result.last_page == 3


def test_first_page_204_is_complete_empty_and_does_not_fetch_page_two() -> None:
    fetcher = FakeFetcher(pages={1: empty_no_content(1)})
    result = _paginator(fetcher).collect(_query())

    assert fetcher.calls == [1]
    assert result.complete is True
    assert result.items == ()
    assert result.records_received == 0
    assert result.reported_total == 0
    assert result.pages_processed == 1
    assert result.last_page == 1


def test_query_does_not_default_business_filters() -> None:
    query = PublicationQuery(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        modality_code=8,
    )
    assert query.uf is None
    assert query.page_size is None
    assert query.modality_code == 8


def test_query_rejects_inverted_dates() -> None:
    with pytest.raises(ValueError, match="end_date"):
        PublicationQuery(
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 1),
            modality_code=1,
        )
