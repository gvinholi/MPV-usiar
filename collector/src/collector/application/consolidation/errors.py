"""Erros explícitos da consolidação. Sem heurística e sem persistência."""


class ConsolidationError(Exception):
    """A consolidação não pôde ser concluída de forma segura."""
