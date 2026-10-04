"""Exceções da integração com a API de consulta do PNCP."""


class PncpError(Exception):
    """Erro da integração PNCP."""


class PncpTimeoutError(PncpError):
    """A requisição excedeu o tempo limite."""


class PncpTransportError(PncpError):
    """Falha de transporte ou conexão com o PNCP."""


class PncpHttpError(PncpError):
    """Resposta HTTP diferente de 200."""

    def __init__(self, message: str, *, status_code: int, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PncpInvalidJsonError(PncpError):
    """O corpo da resposta não é JSON válido."""


class PncpUnexpectedPayloadError(PncpError):
    """O JSON não tem a estrutura de página documentada pelo PNCP."""
