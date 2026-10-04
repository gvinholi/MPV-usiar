"""Adaptador: map_pncp_publication → porta de aplicação."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from collector.application.collection.errors import PublicationMappingError
from collector.domain import Process
from collector.infra.pncp.errors import PncpMappingError
from collector.infra.pncp.mapper import map_pncp_publication


class PncpPublicationMapper:
    def map_publication(
        self,
        item: Mapping[str, object],
        *,
        captured_at: datetime,
    ) -> Process:
        try:
            return map_pncp_publication(item, captured_at=captured_at)
        except PncpMappingError as exc:
            official_id = None
            raw = item.get("numeroControlePNCP") if isinstance(item, Mapping) else None
            if isinstance(raw, str) and raw.strip():
                official_id = raw.strip()
            raise PublicationMappingError(str(exc), official_id=official_id) from exc
