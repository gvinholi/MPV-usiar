"""Resultado auditável de uma consulta de catálogo documental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.domain import ProcurementDocument


@dataclass(frozen=True)
class DocumentCatalogIssue:
    message: str
    official_id: str | None = None
    item_index: int | None = None


@dataclass(frozen=True)
class DocumentCatalogResult:
    query_id: UUID
    process_id: UUID
    round_id: UUID | None
    documents: tuple[ProcurementDocument, ...]
    documents_found: int
    complete: bool
    queried_at: datetime
    errors: tuple[DocumentCatalogIssue, ...]
    failure_reason: str | None = None
