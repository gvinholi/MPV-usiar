"""Construtores de CollectionResult para testes de persistência."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from collector.application import (
    CollectionResult,
    ConsolidatedProcess,
    ConsolidationResult,
    ModalityOutcome,
)
from collector.domain import (
    CollectionRound,
    Process,
    RoundMetrics,
    RoundStatus,
    Source,
    SourceIdentity,
)

STARTED = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
ENDED = datetime(2026, 10, 4, 10, 5, tzinfo=UTC)


def identity(official_id: str, source: Source = Source.PNCP) -> SourceIdentity:
    return SourceIdentity(source=source, official_id=official_id)


def process(
    official_id: str,
    *,
    source: Source = Source.PNCP,
    extra_identities: tuple[SourceIdentity, ...] = (),
    process_id: UUID | None = None,
    last_captured_at: datetime | None = STARTED,
    description: str | None = "manutenção preventiva",
    estimated_value: Decimal | None = Decimal("10000.00"),
    closes_at: datetime | None = datetime(2026, 10, 10, 18, 0, tzinfo=UTC),
    organization_name: str | None = "Prefeitura Exemplo",
) -> Process:
    return Process(
        id=process_id or uuid4(),
        source_identities=(identity(official_id, source),) + extra_identities,
        organization_name=organization_name,
        organization_cnpj="00.000.000/0001-91",
        description=description,
        modality="Pregão Eletrônico",
        published_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        closes_at=closes_at,
        state="SP",
        locality="Campinas",
        estimated_value=estimated_value,
        first_captured_at=last_captured_at,
        last_captured_at=last_captured_at,
    )


def group_from(snapshot: Process) -> ConsolidatedProcess:
    return ConsolidatedProcess(
        process=snapshot,
        identities=snapshot.source_identities,
        observations=(snapshot,),
        observation_count=1,
    )


def outcome(
    modality_code: int = 6,
    *,
    complete: bool = True,
    records_received: int = 1,
    processes_mapped: int = 1,
    pages_processed: int = 1,
    failed_page: int | None = None,
    failure_reason: str | None = None,
) -> ModalityOutcome:
    return ModalityOutcome(
        modality_code=modality_code,
        complete=complete,
        pages_processed=pages_processed,
        records_received=records_received,
        processes_mapped=processes_mapped,
        failed_page=failed_page,
        failure_reason=failure_reason,
    )


def collection_result(
    *snapshots: Process,
    round_id: UUID | None = None,
    status: RoundStatus = RoundStatus.SUCCESS,
    started_at: datetime = STARTED,
    ended_at: datetime = ENDED,
    outcomes: tuple[ModalityOutcome, ...] | None = None,
    raw_processes: tuple[Process, ...] | None = None,
    metrics: RoundMetrics | None = None,
) -> CollectionResult:
    groups = tuple(group_from(snapshot) for snapshot in snapshots)
    raw = raw_processes if raw_processes is not None else snapshots
    if outcomes is None:
        outcomes = (outcome(records_received=len(raw), processes_mapped=len(raw)),)
    if metrics is None:
        metrics = RoundMetrics(
            pages_processed=sum(item.pages_processed for item in outcomes),
            records_collected=sum(item.records_received for item in outcomes),
            unique_processes=len(groups),
            errors=0 if status is RoundStatus.SUCCESS else 1,
        )
    running = CollectionRound.start(
        Source.PNCP, started_at=started_at, id=round_id or uuid4()
    )
    finished = running.finish(status, ended_at=ended_at, metrics=metrics)
    return CollectionResult(
        collection_round=finished,
        processes=raw,
        modality_outcomes=outcomes,
        requested_modalities=tuple(item.modality_code for item in outcomes),
        completed_modalities=tuple(
            item.modality_code for item in outcomes if item.complete
        ),
        incomplete_modalities=tuple(
            item.modality_code for item in outcomes if not item.complete
        ),
        records_received=sum(item.records_received for item in outcomes),
        processes_mapped=len(raw),
        errors=(),
        consolidation=ConsolidationResult(
            observations_received=len(raw),
            unique_processes=len(groups),
            duplicates=len(raw) - len(groups),
            groups=groups,
        ),
    )
