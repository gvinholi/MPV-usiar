"""Erros explícitos da resolução operacional."""


class ResolutionError(Exception):
    """Falha ao resolver estado operacional."""


class InitialScreeningRequiredError(ResolutionError):
    """Document screening sozinho não cria resolução neste estágio."""


class ProcessMismatchError(ResolutionError):
    """Initial e document pertencem a processos diferentes."""


class ProfileMismatchError(ResolutionError):
    """Initial e document usam perfis incompatíveis."""
