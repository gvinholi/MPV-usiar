"""Limites centralizados da extração textual. Sem números mágicos nas bordas."""

from dataclasses import dataclass

# 50 PDFs: os ZIPs reais do piloto tinham 2 e 4 PDFs.
DEFAULT_MAX_PDFS_PER_ARTIFACT = 50
# 100 MiB/member: alinhado ao limite de entry da aquisição.
DEFAULT_MAX_MEMBER_BYTES = 100 * 1024 * 1024
# 1000 páginas: editais longos cabem; evita PDF patológico.
DEFAULT_MAX_PAGES_PER_PDF = 1000
# 5 milhões de caracteres/PDF: ~texto de edital grande, sem blob ilimitado.
DEFAULT_MAX_CHARS_PER_PDF = 5_000_000
# Abaixo deste total o PDF com páginas é tratado como provavelmente escaneado.
DEFAULT_LIKELY_SCANNED_MAX_CHARS = 40


@dataclass(frozen=True)
class TextExtractionPolicy:
    max_pdfs_per_artifact: int = DEFAULT_MAX_PDFS_PER_ARTIFACT
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES
    max_pages_per_pdf: int = DEFAULT_MAX_PAGES_PER_PDF
    max_chars_per_pdf: int = DEFAULT_MAX_CHARS_PER_PDF
    likely_scanned_max_chars: int = DEFAULT_LIKELY_SCANNED_MAX_CHARS

    def __post_init__(self) -> None:
        if self.max_pdfs_per_artifact < 1:
            raise ValueError("max_pdfs_per_artifact deve ser >= 1")
        if self.max_member_bytes < 1:
            raise ValueError("max_member_bytes deve ser >= 1")
        if self.max_pages_per_pdf < 1:
            raise ValueError("max_pages_per_pdf deve ser >= 1")
        if self.max_chars_per_pdf < 1:
            raise ValueError("max_chars_per_pdf deve ser >= 1")
        if self.likely_scanned_max_chars < 0:
            raise ValueError("likely_scanned_max_chars não pode ser negativo")
