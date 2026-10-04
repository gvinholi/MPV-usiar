"""Erros da triagem e da persistência de avaliações."""

from collector.application.persistence.errors import PersistenceError


class ScreeningError(Exception):
    """Falha ao avaliar um snapshot contra um perfil."""


class IncompatibleProfileError(PersistenceError):
    """O perfil code/version já existe com configuração diferente."""
