"""Fakes da coleta — sem HTTP e sem relógio real."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import uuid4

from collector.application import (
    PublicationMappingError,
    PublicationPage,
    PublicationQuery,
)
from collector.domain import Process, Source, SourceIdentity


class ModalityFetcher:
    def __init__(
        self,
        pages: Mapping[int, Mapping[int, PublicationPage]] | None = None,
        errors: Mapping[int, Mapping[int, list[BaseException]]] | None = None,
    ) -> None:
        self.calls: list[tuple[int, int]] = []
        self._pages = {modality: dict(by_page) for modality, by_page in (pages or {}).items()}
        self._errors = {
            modality: {page_n: list(seq) for page_n, seq in by_page.items()}
            for modality, by_page in (errors or {}).items()
        }

    def fetch_page(self, query: PublicationQuery, page_number: int) -> PublicationPage:
        self.calls.append((query.modality_code, page_number))
        pending = self._errors.get(query.modality_code, {}).get(page_number, [])
        if pending:
            raise pending.pop(0)
        return self._pages[query.modality_code][page_number]


class RecordingMapper:
    def __init__(self, fail_ids: frozenset[str] = frozenset()) -> None:
        self.calls: list[tuple[object, datetime]] = []
        self._fail_ids = fail_ids

    def map_publication(
        self,
        item: Mapping[str, object],
        *,
        captured_at: datetime,
    ) -> Process:
        self.calls.append((item, captured_at))
        official_id = str(item.get("numeroControlePNCP") or item.get("id") or "")
        if official_id in self._fail_ids:
            raise PublicationMappingError("item inválido", official_id=official_id or None)
        return Process(
            id=uuid4(),
            source_identities=(SourceIdentity(source=Source.PNCP, official_id=official_id or "x"),),
            first_captured_at=captured_at,
            last_captured_at=captured_at,
        )
