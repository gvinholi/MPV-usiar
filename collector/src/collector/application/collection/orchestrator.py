"""Orquestra uma coleta PNCP em várias modalidades, em sequência."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from collector.application.collection.errors import PublicationMappingError
from collector.application.collection.ports import PublicationMapper
from collector.application.collection.request import CollectionRequest
from collector.application.collection.results import (
    CollectionIssue,
    CollectionResult,
    ModalityOutcome,
)
from collector.application.consolidation import ProcessConsolidator
from collector.application.publications.errors import IncompleteCollectionError
from collector.application.publications.paginator import PublicationPaginator
from collector.application.publications.query import PublicationQuery
from collector.domain import CollectionRound, Process, RoundMetrics, RoundStatus, Source
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


class CollectionOrchestrator:
    def __init__(
        self,
        paginator: PublicationPaginator,
        mapper: PublicationMapper,
        *,
        consolidator: ProcessConsolidator | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self._paginator = paginator
        self._mapper = mapper
        self._consolidator = consolidator or ProcessConsolidator()
        self._clock = clock

    def collect(self, request: CollectionRequest) -> CollectionResult:
        captured_at = self._clock()
        running = CollectionRound.start(Source.PNCP, started_at=captured_at)
        processes: list[Process] = []
        outcomes: list[ModalityOutcome] = []
        issues: list[CollectionIssue] = []

        for modality_code in request.modality_codes:
            outcome, mapped, modality_issues = self._collect_modality(
                request, modality_code, captured_at
            )
            processes.extend(mapped)
            outcomes.append(outcome)
            issues.extend(modality_issues)

        consolidation = self._consolidator.consolidate(processes)
        metrics = _round_metrics(outcomes, issues, consolidation.unique_processes)
        status = _round_status(outcomes, processes)
        finished = running.finish(
            status, ended_at=self._clock(), metrics=metrics
        )
        completed = tuple(
            outcome.modality_code for outcome in outcomes if outcome.complete
        )
        incomplete = tuple(
            outcome.modality_code for outcome in outcomes if not outcome.complete
        )
        return CollectionResult(
            collection_round=finished,
            processes=tuple(processes),
            modality_outcomes=tuple(outcomes),
            requested_modalities=request.modality_codes,
            completed_modalities=completed,
            incomplete_modalities=incomplete,
            records_received=sum(outcome.records_received for outcome in outcomes),
            processes_mapped=len(processes),
            errors=tuple(issues),
            consolidation=consolidation,
        )

    def _collect_modality(
        self,
        request: CollectionRequest,
        modality_code: int,
        captured_at: datetime,
    ) -> tuple[ModalityOutcome, list[Process], list[CollectionIssue]]:
        query = PublicationQuery(
            start_date=request.start_date,
            end_date=request.end_date,
            modality_code=modality_code,
            uf=request.uf,
            page_size=request.page_size,
            dispute_mode_code=request.dispute_mode_code,
            ibge_municipality_code=request.ibge_municipality_code,
            cnpj=request.cnpj,
            administrative_unit_code=request.administrative_unit_code,
            user_id=request.user_id,
        )
        issues: list[CollectionIssue] = []
        try:
            collection = self._paginator.collect(query)
            pagination_failed = False
            failed_page = None
            failure_reason = None
        except IncompleteCollectionError as exc:
            collection = exc.result
            pagination_failed = True
            failed_page = collection.failed_page
            failure_reason = collection.failure_reason or str(exc)
            issues.append(
                CollectionIssue(
                    modality_code=modality_code,
                    message=failure_reason,
                    kind="pagination",
                    failed_page=failed_page,
                )
            )

        mapped, mapping_issues = self._map_items(
            collection.items, modality_code, captured_at
        )
        issues.extend(mapping_issues)
        complete = (not pagination_failed) and collection.complete and not mapping_issues
        outcome = ModalityOutcome(
            modality_code=modality_code,
            complete=complete,
            pages_processed=collection.pages_processed,
            records_received=collection.records_received,
            processes_mapped=len(mapped),
            failed_page=failed_page,
            failure_reason=failure_reason,
            mapping_errors=tuple(mapping_issues),
        )
        return outcome, mapped, issues

    def _map_items(
        self,
        items: tuple[Mapping[str, object], ...],
        modality_code: int,
        captured_at: datetime,
    ) -> tuple[list[Process], list[CollectionIssue]]:
        mapped: list[Process] = []
        issues: list[CollectionIssue] = []
        for index, item in enumerate(items):
            try:
                mapped.append(
                    self._mapper.map_publication(item, captured_at=captured_at)
                )
            except PublicationMappingError as exc:
                issues.append(
                    CollectionIssue(
                        modality_code=modality_code,
                        message=str(exc),
                        kind="mapping",
                        official_id=exc.official_id,
                        item_index=index,
                    )
                )
        return mapped, issues


def _round_metrics(
    outcomes: list[ModalityOutcome],
    issues: list[CollectionIssue],
    unique_processes: int,
) -> RoundMetrics:
    pages_with_error = sum(1 for issue in issues if issue.kind == "pagination")
    return RoundMetrics(
        pages_processed=sum(outcome.pages_processed for outcome in outcomes),
        pages_with_error=pages_with_error,
        records_collected=sum(outcome.records_received for outcome in outcomes),
        unique_processes=unique_processes,
        errors=len(issues),
    )


def _round_status(
    outcomes: list[ModalityOutcome],
    processes: list[Process],
) -> RoundStatus:
    if outcomes and all(outcome.complete for outcome in outcomes):
        return RoundStatus.SUCCESS
    useful = any(
        outcome.complete or outcome.records_received > 0 or outcome.processes_mapped > 0
        for outcome in outcomes
    )
    if useful or processes:
        return RoundStatus.PARTIAL
    return RoundStatus.FAILED
