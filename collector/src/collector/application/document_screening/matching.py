"""Casamento por página com offsets no texto original."""

from __future__ import annotations

from collector.application.document_screening.negation import is_negated
from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.results import (
    DocumentPageRef,
    DocumentScreeningEvidence,
)
from collector.application.document_screening.snippet import context_snippet
from collector.application.screening.matching import find_matches
from collector.application.screening.normalize import tokenize_with_spans
from collector.application.screening.profile import ScreeningProfile


def collect_page_evidence(
    page: DocumentPageRef,
    profile: ScreeningProfile,
    policy: DocumentScreeningPolicy,
) -> tuple[DocumentScreeningEvidence, ...]:
    spans = tokenize_with_spans(page.text)
    tokens = tuple(span.token for span in spans)
    if not tokens:
        return ()
    buckets = (
        ("context", profile.context_terms),
        ("maintenance", profile.maintenance_terms),
        ("sanitization", profile.sanitization_terms),
        ("installation", profile.installation_terms),
        ("purchase", profile.purchase_terms),
        ("parts", profile.parts_terms),
    )
    evidence: list[DocumentScreeningEvidence] = []
    for category, terms in buckets:
        for term in terms:
            for token_start, token_end in find_matches(tokens, term):
                start = spans[token_start].start
                end = spans[token_end - 1].end
                evidence.append(
                    DocumentScreeningEvidence(
                        category=category,
                        configured_term=term,
                        matched_text=page.text[start:end],
                        context_snippet=context_snippet(page.text, start, end, policy),
                        page_number=page.page_number,
                        extraction_page_id=page.extraction_page_id,
                        source_id=page.source_id,
                        source_sha256=page.source_sha256,
                        source_path=page.source_path,
                        artifact_id=page.artifact_id,
                        artifact_sha256=page.artifact_sha256,
                        document_id=page.document_id,
                        negated=is_negated(tokens, token_start, policy),
                        start_offset=start,
                        end_offset=end,
                        token_start=token_start,
                        token_end=token_end,
                    )
                )
    return tuple(evidence)
