"""Precedência da triagem documental. Sem IA e sem score numérico."""

from __future__ import annotations

from collections.abc import Sequence

from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.proximity import has_proximate_pair
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import (
    DocumentCoverage,
    DocumentScreeningEvidence,
)
from collector.domain import ScreeningStatus


def active_evidence(
    evidence: Sequence[DocumentScreeningEvidence],
) -> tuple[DocumentScreeningEvidence, ...]:
    return tuple(item for item in evidence if not item.negated)


def _of(
    evidence: Sequence[DocumentScreeningEvidence], category: str
) -> tuple[DocumentScreeningEvidence, ...]:
    return tuple(item for item in evidence if item.category == category)


def decide_document(
    evidence: Sequence[DocumentScreeningEvidence],
    coverage: DocumentCoverage,
    policy: DocumentScreeningPolicy,
) -> tuple[ScreeningStatus, DocumentReasonCode]:
    """Decisão sobre o conjunto documental.

    HVAC + serviço só contam juntos na mesma página e dentro da janela.
    Ausência de termo não vira descarte. Cobertura incompleta bloqueia
    exclusão isolada.
    """

    active = active_evidence(evidence)
    context = _of(active, "context")
    maintenance = _of(active, "maintenance")
    sanitization = _of(active, "sanitization")
    installation = _of(active, "installation")
    purchase = _of(active, "purchase")
    parts = _of(active, "parts")

    relevant_maintenance = has_proximate_pair(context, maintenance, policy)
    relevant_sanitization = has_proximate_pair(context, sanitization, policy)
    relevant = relevant_maintenance or relevant_sanitization
    mixed_install = relevant and has_proximate_pair(context, installation, policy)
    mixed_supply = relevant and (
        has_proximate_pair(context, purchase, policy)
        or has_proximate_pair(context, parts, policy)
    )
    isolated_install = (
        not relevant
        and bool(context)
        and has_proximate_pair(context, installation, policy)
    )
    isolated_parts = (
        not relevant
        and bool(context)
        and has_proximate_pair(context, parts, policy)
    )
    isolated_purchase = (
        not relevant
        and bool(context)
        and has_proximate_pair(context, purchase, policy)
    )

    if mixed_install:
        return (
            ScreeningStatus.PENDING,
            DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_INSTALLATION,
        )
    if mixed_supply:
        return (
            ScreeningStatus.PENDING,
            DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_SUPPLY,
        )
    if relevant_maintenance:
        return ScreeningStatus.CANDIDATE, DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE
    if relevant_sanitization:
        return ScreeningStatus.CANDIDATE, DocumentReasonCode.DOCUMENT_RELEVANT_SANITIZATION
    if isolated_install or isolated_parts or isolated_purchase:
        if not coverage.complete:
            return ScreeningStatus.PENDING, DocumentReasonCode.DOCUMENT_INCOMPLETE_COVERAGE
        if isolated_install:
            return (
                ScreeningStatus.DISCARDED,
                DocumentReasonCode.DOCUMENT_ISOLATED_INSTALLATION,
            )
        if isolated_parts:
            return (
                ScreeningStatus.DISCARDED,
                DocumentReasonCode.DOCUMENT_ISOLATED_PARTS_SUPPLY,
            )
        return (
            ScreeningStatus.DISCARDED,
            DocumentReasonCode.DOCUMENT_ISOLATED_EQUIPMENT_PURCHASE,
        )
    if context:
        return ScreeningStatus.PENDING, DocumentReasonCode.DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT
    if coverage.pages_considered == 0 or coverage.pages_with_text == 0:
        return ScreeningStatus.PENDING, DocumentReasonCode.DOCUMENT_NO_TEXT
    return ScreeningStatus.PENDING, DocumentReasonCode.DOCUMENT_NO_DECISIVE_EVIDENCE
