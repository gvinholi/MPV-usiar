"""Erros da extração textual. Sem detalhes de biblioteca PDF."""

from collector.application.extraction.reasons import ExtractionReason


class ExtractionError(Exception):
    def __init__(self, message: str, *, reason: ExtractionReason) -> None:
        super().__init__(message)
        self.reason = reason
