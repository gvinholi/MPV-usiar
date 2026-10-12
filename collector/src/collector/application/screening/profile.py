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
    ambiguous_context_terms: tuple[str, ...] = ()
    excluded_context_terms: tuple[str, ...] = ()
    association_window_tokens: int | None = None
    id: UUID | None = None
    active: bool = True

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("profile code é obrigatório")
        if not self.version.strip():
            raise ValueError("profile version é obrigatória")
        if self.association_window_tokens is not None and (
            isinstance(self.association_window_tokens, bool)
            or self.association_window_tokens < 1
        ):
            raise ValueError("association_window_tokens deve ser inteiro positivo")

    @property
    def identity(self) -> str:
        return f"{self.code}/{self.version}"

    def configuration(self) -> dict[str, object]:
        configuration: dict[str, object] = {
            "context_terms": self.context_terms,
            "maintenance_terms": self.maintenance_terms,
            "sanitization_terms": self.sanitization_terms,
            "installation_terms": self.installation_terms,
            "purchase_terms": self.purchase_terms,
            "parts_terms": self.parts_terms,
        }
        # Campos novos são omitidos no perfil legado para manter exatamente o
        # payload persistido de USIAR/v1.
        if self.ambiguous_context_terms:
            configuration["ambiguous_context_terms"] = self.ambiguous_context_terms
        if self.excluded_context_terms:
            configuration["excluded_context_terms"] = self.excluded_context_terms
        if self.association_window_tokens is not None:
            configuration["association_window_tokens"] = self.association_window_tokens
        return configuration
