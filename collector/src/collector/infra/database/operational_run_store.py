"""PostgreSQL para observações e métricas do runner operacional."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.operational import RoundObservation, ScreeningMetrics
from collector.application.persistence.errors import PersistenceError
from collector.infra.database.models import CollectionRoundRow, ProcessObservationRow


class SqlAlchemyOperationalRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_round_observations(self, round_id: UUID) -> tuple[RoundObservation, ...]:
        try:
            with self._session_factory() as session:
                rows = session.execute(
                    select(
                        ProcessObservationRow.id,
                        ProcessObservationRow.process_id,
                        ProcessObservationRow.description,
                    )
                    .where(ProcessObservationRow.round_id == round_id)
                    .order_by(ProcessObservationRow.id)
                )
                return tuple(
                    RoundObservation(
                        observation_id=row.id,
                        process_id=row.process_id,
                        description=row.description,
                    )
                    for row in rows
                )
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao consultar observações da rodada") from exc

    def update_screening_metrics(
        self, round_id: UUID, metrics: ScreeningMetrics
    ) -> None:
        try:
            with self._session_factory.begin() as session:
                exists = session.scalar(
                    select(CollectionRoundRow.id).where(
                        CollectionRoundRow.id == round_id
                    )
                )
                if exists is None:
                    raise PersistenceError(
                        "rodada não encontrada para atualizar métricas"
                    )
                session.execute(
                    update(CollectionRoundRow)
                    .where(CollectionRoundRow.id == round_id)
                    .values(
                        candidates=metrics.candidates,
                        pending=metrics.pending,
                        discarded=metrics.discarded,
                    )
                )
        except PersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao atualizar métricas da rodada") from exc
