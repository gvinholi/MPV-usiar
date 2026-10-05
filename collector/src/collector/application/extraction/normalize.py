"""Normalização mínima do texto extraído. Sem reescrever conteúdo."""


def normalize_extracted_text(value: str) -> str:
    text = value.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text
