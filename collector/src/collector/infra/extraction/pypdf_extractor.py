"""Extractor local de PDF via pypdf. Somente leitura, sem OCR e sem JS."""

from __future__ import annotations

from importlib.metadata import version

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.normalize import normalize_extracted_text
from collector.application.extraction.reasons import ExtractionReason
from collector.domain.text import TextPage

EXTRACTOR_NAME = "pypdf"


class PypdfTextExtractor:
    name = EXTRACTOR_NAME

    def __init__(self, extractor_version: str | None = None) -> None:
        self.version = extractor_version or version("pypdf")

    def extract_pages(self, stream) -> tuple[TextPage, ...]:
        try:
            reader = PdfReader(stream)
        except PdfReadError as exc:
            raise ExtractionError(
                "PDF inválido",
                reason=ExtractionReason.INVALID_PDF,
            ) from exc
        except Exception as exc:
            raise ExtractionError(
                "falha ao abrir PDF",
                reason=ExtractionReason.INVALID_PDF,
            ) from exc
        if reader.is_encrypted:
            raise ExtractionError(
                "PDF criptografado não é aberto",
                reason=ExtractionReason.PDF_ENCRYPTED,
            )
        pages: list[TextPage] = []
        try:
            for index, page in enumerate(reader.pages, start=1):
                raw = page.extract_text() or ""
                text = normalize_extracted_text(raw)
                pages.append(TextPage(page_number=index, text=text, char_count=len(text)))
        except FileNotDecryptedError as exc:
            raise ExtractionError(
                "PDF criptografado não é aberto",
                reason=ExtractionReason.PDF_ENCRYPTED,
            ) from exc
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(
                "falha ao extrair texto do PDF",
                reason=ExtractionReason.EXTRACTION_ERROR,
            ) from exc
        return tuple(pages)
