"""Processo de contratação independente da fonte.

Campos descrevem o negócio, não o payload de uma API. A transformação
PNCP → domínio fica no adaptador de infraestrutura.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from collector.domain.screening import ScreeningStatus
from collector.domain.source import SourceIdentity
from collector.domain.timestamps import require_aware


@dataclass(frozen=True)
class Process:
    id: UUID
    source_identities: tuple[SourceIdentity, ...]
    organization_name: str | None = None
    organization_cnpj: str | None = None
    description: str | None = None
    modality: str | None = None
    published_at: datetime | None = None
    closes_at: datetime | None = None
    state: str | None = None
    locality: str | None = None
    estimated_value: Decimal | None = None
    notice_number: str | None = None
    official_url: str | None = None
    first_captured_at: datetime | None = None
    last_captured_at: datetime | None = None
    screening_status: ScreeningStatus = ScreeningStatus.RAW
    decision_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.source_identities:
            raise ValueError("processo exige ao menos uma identidade oficial da fonte")
        if len(set(self.source_identities)) != len(self.source_identities):
            raise ValueError("identidades oficiais duplicadas")
        if self.estimated_value is not None and not isinstance(
            self.estimated_value, Decimal
        ):
            raise TypeError("estimated_value deve ser Decimal")
        for field_name in (
            "published_at",
            "closes_at",
            "first_captured_at",
            "last_captured_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_aware(value, field_name)
