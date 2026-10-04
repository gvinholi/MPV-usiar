"""Erros da orquestração de coleta. Sem detalhes de transporte HTTP."""


class CollectionRequestError(ValueError):
    """Pedido de coleta inválido."""


class PublicationMappingError(Exception):
    """Falha ao transformar um item bruto em processo de domínio."""

    def __init__(self, message: str, *, official_id: str | None = None) -> None:
        super().__init__(message)
        self.official_id = official_id
