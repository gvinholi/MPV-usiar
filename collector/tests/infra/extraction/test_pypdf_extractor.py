"""Extractor pypdf — fixtures locais, sem rede."""

import io

import pytest

from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.reasons import ExtractionReason
from collector.infra.extraction import EXTRACTOR_NAME, PypdfTextExtractor
from tests.application.extraction.pdf_fixtures import (
    FAKE_PDF_HEADER,
    ONE_PAGE_PDF,
    TWO_PAGE_PDF,
    text_pdf,
)


def test_extracts_known_text() -> None:
    pages = PypdfTextExtractor().extract_pages(io.BytesIO(ONE_PAGE_PDF))
    assert pages[0].page_number == 1
    assert "Hello page one" in pages[0].text


def test_extracts_multiple_pages() -> None:
    pages = PypdfTextExtractor().extract_pages(io.BytesIO(TWO_PAGE_PDF))
    assert len(pages) == 2


def test_blank_page_has_empty_text() -> None:
    pages = PypdfTextExtractor().extract_pages(io.BytesIO(text_pdf("")))
    assert pages[0].text == ""


def test_invalid_pdf() -> None:
    with pytest.raises(ExtractionError) as exc:
        PypdfTextExtractor().extract_pages(io.BytesIO(FAKE_PDF_HEADER))
    assert exc.value.reason is ExtractionReason.INVALID_PDF


def test_extractor_identity() -> None:
    extractor = PypdfTextExtractor()
    assert extractor.name == EXTRACTOR_NAME
    assert extractor.version
