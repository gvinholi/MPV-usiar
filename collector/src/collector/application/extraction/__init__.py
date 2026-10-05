"""Extração textual determinística. Sem OCR, sem IA e sem triagem."""

from collector.application.extraction.extract import ExtractArtifactText
from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.persist import (
    PersistTextExtraction,
    PersistTextExtractionOutcome,
)
from collector.application.extraction.policy import TextExtractionPolicy
from collector.application.extraction.ports import PdfTextExtractor, TextExtractionRepository
from collector.application.extraction.reasons import ExtractionReason
from collector.application.extraction.results import (
    ArtifactTextExtractionResult,
    ExtractionIssue,
    ExtractionMetrics,
    SourceExtraction,
)

__all__ = [
    "ArtifactTextExtractionResult",
    "ExtractArtifactText",
    "ExtractionError",
    "ExtractionIssue",
    "ExtractionMetrics",
    "ExtractionReason",
    "PdfTextExtractor",
    "PersistTextExtraction",
    "PersistTextExtractionOutcome",
    "SourceExtraction",
    "TextExtractionPolicy",
    "TextExtractionRepository",
]
