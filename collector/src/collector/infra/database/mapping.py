"""Tradução entre tipos de aplicação/domínio e linhas de persistência."""

from __future__ import annotations

from collector.application.collection.results import CollectionIssue, ModalityOutcome
from collector.domain import CollectionRound, Process, RoundMetrics, RoundStatus, Source


def mapping_errors_payload(outcome: ModalityOutcome) -> list[dict[str, object | None]]:
    return [_issue_payload(issue) for issue in outcome.mapping_errors]


def _issue_payload(issue: CollectionIssue) -> dict[str, object | None]:
    return {
        "kind": issue.kind,
        "message": issue.message,
        "official_id": issue.official_id,
        "item_index": issue.item_index,
        "failed_page": issue.failed_page,
    }


def round_from_row(
    *,
    id,
    source: str,
    started_at,
    finished_at,
    status: str,
    pages_expected: int,
    pages_processed: int,
    pages_with_error: int,
    records_collected: int,
    unique_processes: int,
    candidates: int,
    selected: int,
    pending: int,
    discarded: int,
    documents_found: int,
    errors: int,
) -> CollectionRound:
    return CollectionRound(
        id=id,
        source=Source(source),
        started_at=started_at,
        ended_at=finished_at,
        status=RoundStatus(status),
        metrics=RoundMetrics(
            pages_expected=pages_expected,
            pages_processed=pages_processed,
            pages_with_error=pages_with_error,
            records_collected=records_collected,
            unique_processes=unique_processes,
            candidates=candidates,
            selected=selected,
            pending=pending,
            discarded=discarded,
            documents_found=documents_found,
            errors=errors,
        ),
    )


def snapshot_fields(process: Process) -> dict[str, object]:
    return {
        "captured_at": process.last_captured_at,
        "organization_name": process.organization_name,
        "organization_cnpj": process.organization_cnpj,
        "description": process.description,
        "modality": process.modality,
        "published_at": process.published_at,
        "closes_at": process.closes_at,
        "state": process.state,
        "locality": process.locality,
        "estimated_value": process.estimated_value,
        "notice_number": process.notice_number,
        "official_url": process.official_url,
    }
