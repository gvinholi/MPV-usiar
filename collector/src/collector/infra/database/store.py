"""Repositório PostgreSQL da coleta. SQLAlchemy não sai desta camada."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.collection.results import ModalityOutcome
from collector.application.persistence.errors import PersistenceError
from collector.domain import CollectionRound, Process, Source, SourceIdentity
from collector.infra.database.mapping import (
    mapping_errors_payload,
    round_from_row,
    snapshot_fields,
)
from collector.infra.database.models import (
    CollectionRoundRow,
    ModalityOutcomeRow,
    ProcessObservationRow,
    ProcessRow,
    SourceIdentityRow,
)


class SqlAlchemyCollectionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @contextmanager
    def transaction(self):
        session = self._session_factory()
        self._session = session
        try:
            yield
            session.commit()
        except PersistenceError:
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise PersistenceError("falha inesperada na persistência") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            self._session = None

    def get_round(self, round_id: UUID) -> CollectionRound | None:
        row = self._require_session().get(CollectionRoundRow, round_id)
        if row is None:
            return None
        return round_from_row(
            id=row.id,
            source=row.source,
            started_at=row.started_at,
            finished_at=row.finished_at,
            status=row.status,
            pages_expected=row.pages_expected,
            pages_processed=row.pages_processed,
            pages_with_error=row.pages_with_error,
            records_collected=row.records_collected,
            unique_processes=row.unique_processes,
            candidates=row.candidates,
            selected=row.selected,
            pending=row.pending,
            discarded=row.discarded,
            documents_found=row.documents_found,
            errors=row.errors,
        )

    def find_process_ids_by_identities(
        self, identities: Sequence[SourceIdentity]
    ) -> dict[SourceIdentity, UUID]:
        if not identities:
            return {}
        pairs = [(identity.source.value, identity.official_id) for identity in identities]
        rows = self._require_session().scalars(
            select(SourceIdentityRow).where(
                tuple_(SourceIdentityRow.source, SourceIdentityRow.official_id).in_(pairs)
            )
        )
        found: dict[SourceIdentity, UUID] = {}
        for row in rows:
            found[SourceIdentity(source=Source(row.source), official_id=row.official_id)] = (
                row.process_id
            )
        return found

    def insert_round(
        self, collection_round: CollectionRound, *, created_at: datetime
    ) -> None:
        metrics = collection_round.metrics
        self._require_session().add(
            CollectionRoundRow(
                id=collection_round.id,
                source=collection_round.source.value,
                started_at=collection_round.started_at,
                finished_at=collection_round.ended_at,
                status=collection_round.status.value,
                pages_expected=metrics.pages_expected,
                pages_processed=metrics.pages_processed,
                pages_with_error=metrics.pages_with_error,
                records_collected=metrics.records_collected,
                unique_processes=metrics.unique_processes,
                candidates=metrics.candidates,
                selected=metrics.selected,
                pending=metrics.pending,
                discarded=metrics.discarded,
                documents_found=metrics.documents_found,
                errors=metrics.errors,
                created_at=created_at,
            )
        )

    def insert_modality_outcome(
        self,
        round_id: UUID,
        outcome: ModalityOutcome,
        *,
        created_at: datetime,
    ) -> None:
        self._require_session().add(
            ModalityOutcomeRow(
                id=uuid4(),
                round_id=round_id,
                modality_code=outcome.modality_code,
                complete=outcome.complete,
                pages_processed=outcome.pages_processed,
                records_received=outcome.records_received,
                processes_mapped=outcome.processes_mapped,
                failed_page=outcome.failed_page,
                failure_reason=outcome.failure_reason,
                mapping_errors=mapping_errors_payload(outcome),
                created_at=created_at,
            )
        )

    def insert_process(self, process_id: UUID, *, created_at: datetime) -> None:
        self._require_session().add(
            ProcessRow(id=process_id, created_at=created_at, updated_at=created_at)
        )

    def touch_process(self, process_id: UUID, *, updated_at: datetime) -> None:
        row = self._require_session().get(ProcessRow, process_id)
        if row is None:
            raise PersistenceError("processo persistente não encontrado")
        row.updated_at = updated_at

    def insert_identity(
        self,
        process_id: UUID,
        identity: SourceIdentity,
        *,
        created_at: datetime,
    ) -> None:
        self._require_session().add(
            SourceIdentityRow(
                id=uuid4(),
                process_id=process_id,
                source=identity.source.value,
                official_id=identity.official_id,
                created_at=created_at,
            )
        )

    def insert_observation(
        self,
        *,
        observation_id: UUID,
        process_id: UUID,
        round_id: UUID,
        source: Source,
        snapshot: Process,
        created_at: datetime,
    ) -> None:
        self._require_session().add(
            ProcessObservationRow(
                id=observation_id,
                process_id=process_id,
                round_id=round_id,
                source=source.value,
                created_at=created_at,
                **snapshot_fields(snapshot),
            )
        )

    def has_observation(self, round_id: UUID, process_id: UUID) -> bool:
        session = self._require_session()
        row = session.scalar(
            select(ProcessObservationRow.id).where(
                ProcessObservationRow.round_id == round_id,
                ProcessObservationRow.process_id == process_id,
            )
        )
        return row is not None

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
