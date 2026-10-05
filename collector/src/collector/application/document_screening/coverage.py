"""Cobertura explícita. Sem score probabilístico."""

from __future__ import annotations

from collections.abc import Sequence

from collector.application.document_screening.results import (
    DocumentCoverage,
    DocumentPageRef,
    DocumentSourceRef,
)

_FAILED = "FAILED"
_UNSUPPORTED = "UNSUPPORTED"
_LIKELY_SCANNED = "LIKELY_SCANNED"


def measure_coverage(
    pages: Sequence[DocumentPageRef],
    sources: Sequence[DocumentSourceRef],
) -> DocumentCoverage:
    document_ids = {item.document_id for item in sources if item.document_id is not None}
    if not document_ids:
        document_ids = {item.document_id for item in pages if item.document_id is not None}
    likely = sum(1 for item in sources if item.likely_scanned or item.status == _LIKELY_SCANNED)
    failed = sum(1 for item in sources if item.status == _FAILED)
    unsupported = sum(1 for item in sources if item.status == _UNSUPPORTED)
    pages_with_text = sum(1 for page in pages if page.text.strip())
    complete = failed == 0 and unsupported == 0 and likely == 0
    return DocumentCoverage(
        documents_considered=len(document_ids),
        sources_considered=len(sources),
        pages_considered=len(pages),
        pages_with_text=pages_with_text,
        likely_scanned_sources=likely,
        failed_sources=failed,
        unsupported_sources=unsupported,
        complete=complete,
    )
