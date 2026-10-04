"""Configuração de persistência. Único ponto que lê DATABASE_URL."""

from __future__ import annotations

import os

from collector.application.persistence.errors import PersistenceError


class PersistenceConfigError(PersistenceError):
    """DATABASE_URL ausente ou inválida."""


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise PersistenceConfigError("DATABASE_URL não configurada")
    return url
