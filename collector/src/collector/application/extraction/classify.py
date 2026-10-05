"""Heurística conservadora de texto digital vs. provavelmente escaneado."""

from collector.application.extraction.policy import TextExtractionPolicy
from collector.domain.text import ExtractionStatus, TextPage


def page_has_text(page: TextPage) -> bool:
    return page.text.strip() != ""


def classify_extraction(
    pages: tuple[TextPage, ...],
    policy: TextExtractionPolicy,
) -> tuple[ExtractionStatus, bool]:
    del policy
    if not pages:
        return ExtractionStatus.EMPTY_TEXT, False
    if not any(page_has_text(page) for page in pages):
        return ExtractionStatus.LIKELY_SCANNED, True
    return ExtractionStatus.DIGITAL_TEXT, False
