"""Fetcher em memória para testes — sem HTTP e sem sleep."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from collector.application import PublicationPage, PublicationQuery


class FakeFetcher:
    def __init__(
        self,
        pages: Mapping[int, PublicationPage] | None = None,
        errors: Mapping[int, list[BaseException]] | None = None,
    ) -> None:
        self.calls: list[int] = []
        self._pages = dict(pages or {})
        self._errors = {page: list(seq) for page, seq in (errors or {}).items()}

    def fetch_page(self, query: PublicationQuery, page: int) -> PublicationPage:
        self.calls.append(page)
        pending = self._errors.get(page, [])
        if pending:
            error = pending.pop(0)
            raise error
        return self._pages[page]


def page(
    number: int,
    *,
    items: tuple[Mapping[str, object], ...] = (),
    total_registros: int | None = None,
    total_paginas: int,
    paginas_restantes: int | None = None,
    empty: bool | None = None,
) -> PublicationPage:
    data = items
    remaining = (
        total_paginas - number if paginas_restantes is None else paginas_restantes
    )
    return PublicationPage(
        data=data,
        total_registros=len(data) if total_registros is None else total_registros,
        total_paginas=total_paginas,
        numero_pagina=number,
        paginas_restantes=remaining,
        empty=len(data) == 0 if empty is None else empty,
    )


def empty_no_content(requested_page: int = 1) -> PublicationPage:
    return PublicationPage(
        data=(),
        total_registros=0,
        total_paginas=0,
        numero_pagina=requested_page,
        paginas_restantes=0,
        empty=True,
    )


def recording_waiter() -> tuple[list[float], Callable[[float], None]]:
    delays: list[float] = []

    def waiter(seconds: float) -> None:
        delays.append(seconds)

    return delays, waiter
