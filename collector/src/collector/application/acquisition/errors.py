"""Erros da aquisição. Sem detalhes de cliente HTTP ou filesystem."""

from collector.application.acquisition.reasons import AcquisitionReason


class AcquisitionError(Exception):
    """Falha técnica ao adquirir um artefato."""

    def __init__(self, message: str, *, reason: AcquisitionReason) -> None:
        super().__init__(message)
        self.reason = reason
