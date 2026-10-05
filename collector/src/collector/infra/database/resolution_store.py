"""Repositório PostgreSQL da resolução operacional."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from collector.application.persistence.errors import PersistenceError
from collector.application.resolution.results import OperationalResolution
from collector.domain import ScreeningStatus
from collector.infra.database.models import OperationalResolutionRow
from collector.infra.database.resolution_mapping import resolution_from_row

_LATEST = (
    OperationalResolutionRow.resolved_at.desc(),
    OperationalResolutionRow.created_at.desc(),
    OperationalResolutionRow.resolution_fingerprint.desc(),
)


class SqlAlchemyOperationalResolutionRepository:
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

    def get_resolution(
        self,
        process_id: UUID,
        profile_id: UUID,
        resolver_engine_version: str,
        resolution_fingerprint: str,
    ) -> OperationalResolution | None:
        row = self._require_session().scalar(
            select(OperationalResolutionRow)
            .options(selectinload(OperationalResolutionRow.profile))
            .where(
                OperationalResolutionRow.process_id == process_id,
                OperationalResolutionRow.profile_id == profile_id,
                OperationalResolutionRow.resolver_engine_version
                == resolver_engine_version,
                OperationalResolutionRow.resolution_fingerprint
                == resolution_fingerprint,
            )
        )
        if row is None:
            return None
        return resolution_from_row(row)

    def insert_resolution(
        self, resolution: OperationalResolution, *, created_at: datetime
    ) -> None:
        if resolution.profile_id is None:
            raise PersistenceError("resolução persistida exige profile_id")
        self._require_session().add(
            OperationalResolutionRow(
                id=resolution.id,
                process_id=resolution.process_id,
                profile_id=resolution.profile_id,
                initial_evaluation_id=resolution.initial_evaluation_id,
                document_evaluation_id=resolution.document_evaluation_id,
                resolver_engine_version=resolution.resolver_engine_version,
                resolution_fingerprint=resolution.resolution_fingerprint,
                state=resolution.state.value,
                reason_code=resolution.reason_code.value,
                reason_text=resolution.reason_text,
                rule_code=resolution.rule_code.value,
                coverage_complete=resolution.coverage_complete,
                state_diverged=resolution.state_diverged,
                reason_diverged=resolution.reason_diverged,
                initial_state=resolution.initial_state.value,
                document_state=(
                    None
                    if resolution.document_state is None
                    else resolution.document_state.value
                ),
                resolved_at=resolution.resolved_at,
                created_at=created_at,
            )
        )

    def list_resolutions_for_process(
        self, process_id: UUID
    ) -> tuple[OperationalResolution, ...]:
        rows = self._require_session().scalars(
            select(OperationalResolutionRow)
            .options(selectinload(OperationalResolutionRow.profile))
            .where(OperationalResolutionRow.process_id == process_id)
            .order_by(*_LATEST)
        )
        return tuple(resolution_from_row(row) for row in rows)

    def latest_resolution(
        self, process_id: UUID, profile_id: UUID | None = None
    ) -> OperationalResolution | None:
        stmt = (
            select(OperationalResolutionRow)
            .options(selectinload(OperationalResolutionRow.profile))
            .where(OperationalResolutionRow.process_id == process_id)
        )
        if profile_id is not None:
            stmt = stmt.where(OperationalResolutionRow.profile_id == profile_id)
        row = self._require_session().scalar(stmt.order_by(*_LATEST).limit(1))
        if row is None:
            return None
        return resolution_from_row(row)

    def list_current_resolutions(
        self, *, state: ScreeningStatus | None = None
    ) -> tuple[OperationalResolution, ...]:
        session = self._require_session()
        ranked = (
            select(
                OperationalResolutionRow.id.label("id"),
                func.row_number()
                .over(
                    partition_by=OperationalResolutionRow.process_id,
                    order_by=_LATEST,
                )
                .label("rn"),
            )
        ).subquery()
        latest_ids = select(ranked.c.id).where(ranked.c.rn == 1)
        stmt = (
            select(OperationalResolutionRow)
            .options(selectinload(OperationalResolutionRow.profile))
            .where(OperationalResolutionRow.id.in_(latest_ids))
            .order_by(*_LATEST)
        )
        if state is not None:
            stmt = stmt.where(OperationalResolutionRow.state == state.value)
        return tuple(resolution_from_row(row) for row in session.scalars(stmt))

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
