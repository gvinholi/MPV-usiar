"""Força semântica da triagem documental. Sem pesos numéricos."""

from enum import Enum

from collector.application.document_screening.reasons import DocumentReasonCode


class DocumentStrength(Enum):
    POSITIVE_DECISIVE = "POSITIVE_DECISIVE"
    MIXED_DECISIVE = "MIXED_DECISIVE"
    NEGATIVE_DECISIVE = "NEGATIVE_DECISIVE"
    NON_DECISIVE = "NON_DECISIVE"


_POSITIVE = frozenset(
    {
        DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE,
        DocumentReasonCode.DOCUMENT_RELEVANT_SANITIZATION,
    }
)
_MIXED = frozenset(
    {
        DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_INSTALLATION,
        DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_SUPPLY,
    }
)
_NEGATIVE = frozenset(
    {
        DocumentReasonCode.DOCUMENT_ISOLATED_INSTALLATION,
        DocumentReasonCode.DOCUMENT_ISOLATED_EQUIPMENT_PURCHASE,
        DocumentReasonCode.DOCUMENT_ISOLATED_PARTS_SUPPLY,
    }
)


def document_strength(reason: DocumentReasonCode) -> DocumentStrength:
    if reason in _POSITIVE:
        return DocumentStrength.POSITIVE_DECISIVE
    if reason in _MIXED:
        return DocumentStrength.MIXED_DECISIVE
    if reason in _NEGATIVE:
        return DocumentStrength.NEGATIVE_DECISIVE
    return DocumentStrength.NON_DECISIVE
