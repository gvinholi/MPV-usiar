"""Erros da coleta paginada. Não são erros de transporte HTTP."""

from __future__ import annotations

from collector.application.publications.results import PublicationCollection


class FetchError(Exception):
    """Falha ao obter uma página."""


class TransientFetchError(FetchError):
    """Falha potencialmente transitória (timeout, conexão, 429, 5xx)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PermanentFetchError(FetchError):
    """Falha que não deve ser retentada (4xx permanente, JSON, payload)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IncompleteCollectionError(Exception):
    """A consulta não terminou completa. O progresso parcial está em `result`."""

    def __init__(self, message: str, *, result: PublicationCollection) -> None:
        super().__init__(message)
        self.result = result
        if result.complete:
            raise ValueError("IncompleteCollectionError exige result.complete is False")
