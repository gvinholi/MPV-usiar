"""Erros do catálogo documental. Sem detalhes HTTP."""


class DocumentCatalogError(Exception):
    """Falha ao catalogar documentos de um processo."""


class DocumentMappingError(Exception):
    """Falha ao traduzir um item bruto em documento de domínio."""

    def __init__(self, message: str, *, official_id: str | None = None) -> None:
        super().__init__(message)
        self.official_id = official_id


class DocumentIdentityConflictError(DocumentCatalogError):
    """A identidade oficial do documento já pertence a outro processo."""
