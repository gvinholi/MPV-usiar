"""Erros de persistência da coleta. Sem detalhes de driver SQL."""


class PersistenceError(Exception):
    """Falha ao persistir o resultado de uma coleta."""


class IdentityConflictError(PersistenceError):
    """Identidades do grupo apontam para mais de um processo persistente."""

    def __init__(self, message: str, *, process_ids: tuple) -> None:
        super().__init__(message)
        self.process_ids = process_ids


class IncompatibleRoundError(PersistenceError):
    """A rodada já existe no banco com estado diferente do resultado atual."""
