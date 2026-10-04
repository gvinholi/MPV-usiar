"""Perfil configurável de triagem. Termos não pertencem ao motor."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ScreeningProfile:
    code: str
    name: str
    version: str
    context_terms: tuple[str, ...]
    maintenance_terms: tuple[str, ...]
    sanitization_terms: tuple[str, ...]
    installation_terms: tuple[str, ...]
    purchase_terms: tuple[str, ...]
    parts_terms: tuple[str, ...]
    id: UUID | None = None
    active: bool = True

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("profile code é obrigatório")
        if not self.version.strip():
            raise ValueError("profile version é obrigatória")

    @property
    def identity(self) -> str:
        return f"{self.code}/{self.version}"

    def configuration(self) -> dict[str, tuple[str, ...]]:
        return {
            "context_terms": self.context_terms,
            "maintenance_terms": self.maintenance_terms,
            "sanitization_terms": self.sanitization_terms,
            "installation_terms": self.installation_terms,
            "purchase_terms": self.purchase_terms,
            "parts_terms": self.parts_terms,
        }
