"""Resultado estruturado de uma coleta multi-modalidade."""

from __future__ import annotations

from dataclasses import dataclass

from collector.domain import CollectionRound, Process


@dataclass(frozen=True)
class CollectionIssue:
    modality_code: int
    message: str
    kind: str
    official_id: str | None = None
    item_index: int | None = None
    failed_page: int | None = None


@dataclass(frozen=True)
class ModalityOutcome:
    modality_code: int
    complete: bool
    pages_processed: int
    records_received: int
    processes_mapped: int
    failed_page: int | None = None
    failure_reason: str | None = None
    mapping_errors: tuple[CollectionIssue, ...] = ()


@dataclass(frozen=True)
class CollectionResult:
    collection_round: CollectionRound
    processes: tuple[Process, ...]
    modality_outcomes: tuple[ModalityOutcome, ...]
    requested_modalities: tuple[int, ...]
    completed_modalities: tuple[int, ...]
    incomplete_modalities: tuple[int, ...]
    records_received: int
    processes_mapped: int
    errors: tuple[CollectionIssue, ...]
