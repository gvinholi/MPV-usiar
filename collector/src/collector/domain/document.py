"""Documento de contratação. Independente do payload de uma API."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.domain.source import Source
from collector.domain.timestamps import require_aware


@dataclass(frozen=True)
class SourceDocumentIdentity:
    """Identidade oficial de um documento em uma fonte.

    O identificador é o da fonte, não o título nem a URL.
    """

    source: Source
    official_id: str

    def __post_init__(self) -> None:
        official_id = self.official_id.strip()
        if not official_id:
            raise ValueError("id oficial do documento é obrigatório")
        object.__setattr__(self, "official_id", official_id)


@dataclass(frozen=True)
class ProcurementDocument:
    id: UUID
    process_id: UUID
    identity: SourceDocumentIdentity
    title: str | None = None
    document_type: str | None = None
    document_type_id: int | None = None
    document_type_description: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    active: bool | None = None
    sequence: int | None = None

    def __post_init__(self) -> None:
        if self.published_at is not None:
            require_aware(self.published_at, "published_at")
