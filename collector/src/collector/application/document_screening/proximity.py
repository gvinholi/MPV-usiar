"""Proximidade determinística: mesma página e janela de tokens."""

from __future__ import annotations

from collections.abc import Sequence

from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.results import DocumentScreeningEvidence


def token_distance(left: DocumentScreeningEvidence, right: DocumentScreeningEvidence) -> int:
    if left.page_number != right.page_number:
        raise ValueError("distância só é definida na mesma página")
    if left.extraction_page_id != right.extraction_page_id:
        raise ValueError("distância exige a mesma página extraída")
    if left.token_end <= right.token_start:
        return right.token_start - left.token_end
    if right.token_end <= left.token_start:
        return left.token_start - right.token_end
    return 0


def are_proximate(
    left: DocumentScreeningEvidence,
    right: DocumentScreeningEvidence,
    policy: DocumentScreeningPolicy,
) -> bool:
    if left.extraction_page_id != right.extraction_page_id:
        return False
    if left.page_number != right.page_number:
        return False
    return token_distance(left, right) <= policy.proximity_token_window


def has_proximate_pair(
    left_items: Sequence[DocumentScreeningEvidence],
    right_items: Sequence[DocumentScreeningEvidence],
    policy: DocumentScreeningPolicy,
) -> bool:
    return any(are_proximate(left, right, policy) for left in left_items for right in right_items)
