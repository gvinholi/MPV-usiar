"""Utilitários de tempo do domínio.

Timestamps do domínio são timezone-aware. O domínio não assume
America/Sao_Paulo; conversão para exibição fica nas bordas.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field} deve ser timezone-aware")
