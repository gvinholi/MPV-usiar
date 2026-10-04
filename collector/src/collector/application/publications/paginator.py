"""Paginação sequencial de uma consulta. Sem concorrência e sem rate limiting."""

from __future__ import annotations

from collections.abc import Mapping

from collector.application.publications.errors import (
    FetchError,
    IncompleteCollectionError,
)
from collector.application.publications.ports import PublicationPageFetcher
from collector.application.publications.query import PublicationQuery
from collector.application.publications.results import PublicationCollection, PublicationPage
from collector.application.publications.retry import RetryPolicy, Waiter, default_waiter, retry_call

DEFAULT_MAX_PAGES = 200


def _is_empty_no_content(page: PublicationPage) -> bool:
    return (
        page.empty
        and page.total_registros == 0
        and page.total_paginas == 0
        and page.paginas_restantes == 0
        and page.data == ()
    )


def _metadata_issue(
    page: PublicationPage,
    requested_page: int,
    previous_total_paginas: int | None,
    seen_pages: set[int],
) -> str | None:
    if page.numero_pagina != requested_page:
        return (
            f"página retornada {page.numero_pagina} difere da solicitada {requested_page}"
        )
    if page.numero_pagina in seen_pages:
        return f"página {page.numero_pagina} repetida"
    if page.total_paginas > 0:
        expected_remaining = page.total_paginas - page.numero_pagina
        if page.paginas_restantes != expected_remaining:
            return (
                "paginas_restantes incompatível com numero_pagina/total_paginas "
                f"(pagina={page.numero_pagina}, total={page.total_paginas}, "
                f"restantes={page.paginas_restantes})"
            )
        if page.numero_pagina > page.total_paginas:
            return "numero_pagina maior que total_paginas"
    if previous_total_paginas is not None and previous_total_paginas > 0:
        if page.total_paginas == 0:
            return "total_paginas zerou após páginas anteriores"
        if page.total_paginas < previous_total_paginas:
            return (
                f"total_paginas diminuiu de {previous_total_paginas} "
                f"para {page.total_paginas}"
            )
    return None


class PublicationPaginator:
    def __init__(
        self,
        fetcher: PublicationPageFetcher,
        *,
        retry_policy: RetryPolicy | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
        waiter: Waiter = default_waiter,
    ) -> None:
        if max_pages < 1:
            raise ValueError("max_pages deve ser >= 1")
        self._fetcher = fetcher
        self._retry_policy = retry_policy or RetryPolicy()
        self._max_pages = max_pages
        self._waiter = waiter

    def collect(self, query: PublicationQuery) -> PublicationCollection:
        items: list[Mapping[str, object]] = []
        seen_pages: set[int] = set()
        previous_total_paginas: int | None = None
        last_page: int | None = None
        reported_total: int | None = None
        pages_processed = 0

        for requested in range(1, self._max_pages + 1):
            try:
                page = self._fetch(query, requested)
            except FetchError as exc:
                raise IncompleteCollectionError(
                    f"falha ao obter a página {requested}",
                    result=_partial(
                        items,
                        pages_processed=pages_processed,
                        last_page=last_page,
                        reported_total=reported_total,
                        failed_page=requested,
                        reason=str(exc),
                    ),
                ) from exc

            if requested > 1 and _is_empty_no_content(page):
                raise IncompleteCollectionError(
                    f"204/vazio inesperado na página {requested} após páginas restantes",
                    result=_partial(
                        items,
                        pages_processed=pages_processed,
                        last_page=last_page,
                        reported_total=reported_total,
                        failed_page=requested,
                        reason="resposta vazia incompatível com páginas restantes",
                    ),
                )

            issue = _metadata_issue(
                page, requested, previous_total_paginas, seen_pages
            )
            if issue is not None:
                raise IncompleteCollectionError(
                    issue,
                    result=_partial(
                        items,
                        pages_processed=pages_processed,
                        last_page=last_page,
                        reported_total=reported_total,
                        failed_page=requested,
                        reason=issue,
                    ),
                )

            items.extend(page.data)
            seen_pages.add(page.numero_pagina)
            pages_processed += 1
            last_page = page.numero_pagina
            reported_total = page.total_registros
            if page.total_paginas > 0:
                previous_total_paginas = page.total_paginas

            if requested == 1 and _is_empty_no_content(page):
                return _complete(items, pages_processed, last_page, reported_total)
            if page.paginas_restantes == 0:
                return _complete(items, pages_processed, last_page, reported_total)

        raise IncompleteCollectionError(
            f"limite de segurança de {self._max_pages} páginas atingido",
            result=_partial(
                items,
                pages_processed=pages_processed,
                last_page=last_page,
                reported_total=reported_total,
                failed_page=None,
                reason=f"max_pages={self._max_pages}",
            ),
        )

    def _fetch(self, query: PublicationQuery, page: int) -> PublicationPage:
        def operation() -> PublicationPage:
            return self._fetcher.fetch_page(query, page)

        return retry_call(operation, self._retry_policy, self._waiter)  # type: ignore[return-value]


def _complete(
    items: list[Mapping[str, object]],
    pages_processed: int,
    last_page: int | None,
    reported_total: int | None,
) -> PublicationCollection:
    return PublicationCollection(
        items=tuple(items),
        pages_processed=pages_processed,
        records_received=len(items),
        reported_total=reported_total,
        first_page=1,
        last_page=last_page,
        complete=True,
    )


def _partial(
    items: list[Mapping[str, object]],
    *,
    pages_processed: int,
    last_page: int | None,
    reported_total: int | None,
    failed_page: int | None,
    reason: str,
) -> PublicationCollection:
    return PublicationCollection(
        items=tuple(items),
        pages_processed=pages_processed,
        records_received=len(items),
        reported_total=reported_total,
        first_page=1,
        last_page=last_page,
        complete=False,
        failed_page=failed_page,
        failure_reason=reason,
    )
