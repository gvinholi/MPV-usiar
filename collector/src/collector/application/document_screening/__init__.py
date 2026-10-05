"""Triagem documental determinística. Independente da triagem inicial."""

from collector.application.document_screening.compare import (
    DivergenceKind,
    ScreeningComparison,
    compare_screenings,
)
from collector.application.document_screening.engine import DocumentScreeningEngine
from collector.application.document_screening.errors import DocumentScreeningError
from collector.application.document_screening.evaluate import EvaluateDocumentScreening
from collector.application.document_screening.fingerprint import document_set_fingerprint
from collector.application.document_screening.persist import (
    PersistDocumentScreening,
    PersistDocumentScreeningOutcome,
)
from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.ports import DocumentScreeningRepository
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import (
    DOCUMENT_ENGINE_VERSION,
    DocumentCoverage,
    DocumentPageRef,
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
    DocumentScreeningEvidence,
    DocumentScreeningSummary,
    DocumentSourceRef,
    summarize_document_evaluations,
)

__all__ = [
    "DOCUMENT_ENGINE_VERSION",
    "DivergenceKind",
    "DocumentCoverage",
    "DocumentPageRef",
    "DocumentReasonCode",
    "DocumentScreeningCorpus",
    "DocumentScreeningEngine",
    "DocumentScreeningError",
    "DocumentScreeningEvaluation",
    "DocumentScreeningEvidence",
    "DocumentScreeningPolicy",
    "DocumentScreeningRepository",
    "DocumentScreeningSummary",
    "DocumentSourceRef",
    "EvaluateDocumentScreening",
    "PersistDocumentScreening",
    "PersistDocumentScreeningOutcome",
    "ScreeningComparison",
    "compare_screenings",
    "document_set_fingerprint",
    "summarize_document_evaluations",
]
