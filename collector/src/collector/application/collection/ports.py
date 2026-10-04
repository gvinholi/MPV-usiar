"""Porta de transformação de item bruto → processo. Sem HTTP."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from collector.domain import Process


class PublicationMapper(Protocol):
    def map_publication(
        self,
        item: Mapping[str, object],
        *,
        captured_at: datetime,
    ) -> Process:
        """Traduz um item externo. Levanta PublicationMappingError se inválido."""
