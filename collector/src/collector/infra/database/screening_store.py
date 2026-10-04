"""Repositório PostgreSQL da triagem."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.persistence.errors import PersistenceError
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.results import ScreeningEvaluation
from collector.infra.database.models import (
    ScreeningEvaluationRow,
    ScreeningEvidenceRow,
    ScreeningProfileRow,
)
from collector.infra.database.screening_mapping import (
    evaluation_from_row,
    profile_configuration_payload,
    profile_from_payload,
)


class SqlAlchemyScreeningRepository:
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

    def get_profile(self, code: str, version: str) -> ScreeningProfile | None:
        row = self._require_session().scalar(
            select(ScreeningProfileRow).where(
                ScreeningProfileRow.code == code,
                ScreeningProfileRow.version == version,
            )
        )
        if row is None:
            return None
        return profile_from_payload(
            id=row.id,
            code=row.code,
            name=row.name,
            version=row.version,
            active=row.active,
            configuration=row.configuration,
        )

    def insert_profile(self, profile: ScreeningProfile, *, created_at: datetime) -> None:
        if profile.id is None:
            raise PersistenceError("perfil persistido exige id")
        self._require_session().add(
            ScreeningProfileRow(
                id=profile.id,
                code=profile.code,
                name=profile.name,
                version=profile.version,
                active=profile.active,
                configuration=profile_configuration_payload(profile),
                created_at=created_at,
            )
        )

    def get_evaluation(
        self,
        observation_id: UUID,
        profile_id: UUID,
        engine_version: str,
    ) -> ScreeningEvaluation | None:
        row = self._require_session().scalar(
            select(ScreeningEvaluationRow).where(
                ScreeningEvaluationRow.observation_id == observation_id,
                ScreeningEvaluationRow.profile_id == profile_id,
                ScreeningEvaluationRow.engine_version == engine_version,
            )
        )
        if row is None:
            return None
        return self._to_evaluation(row)

    def insert_evaluation(
        self, evaluation: ScreeningEvaluation, *, created_at: datetime
    ) -> None:
        if evaluation.profile_id is None:
            raise PersistenceError("avaliação persistida exige profile_id")
        session = self._require_session()
        session.add(
            ScreeningEvaluationRow(
                id=evaluation.id,
                process_id=evaluation.process_id,
                observation_id=evaluation.observation_id,
                profile_id=evaluation.profile_id,
                state=evaluation.state.value,
                reason_code=evaluation.reason_code.value,
                reason_text=evaluation.reason_text,
                evaluated_at=evaluation.evaluated_at,
                engine_version=evaluation.engine_version,
                created_at=created_at,
            )
        )
        for item in evaluation.evidence:
            session.add(
                ScreeningEvidenceRow(
                    id=uuid4(),
                    evaluation_id=evaluation.id,
                    category=item.category,
                    configured_term=item.configured_term,
                    field=item.field,
                    matched_text=item.matched_text,
                    created_at=created_at,
                )
            )

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[ScreeningEvaluation, ...]:
        rows = self._require_session().scalars(
            select(ScreeningEvaluationRow)
            .where(ScreeningEvaluationRow.process_id == process_id)
            .order_by(ScreeningEvaluationRow.evaluated_at)
        )
        return tuple(self._to_evaluation(row) for row in rows)

    def _to_evaluation(self, row: ScreeningEvaluationRow) -> ScreeningEvaluation:
        return evaluation_from_row(
            id=row.id,
            process_id=row.process_id,
            observation_id=row.observation_id,
            profile_id=row.profile_id,
            profile_code=row.profile.code,
            profile_version=row.profile.version,
            state=row.state,
            reason_code=row.reason_code,
            reason_text=row.reason_text,
            evaluated_at=row.evaluated_at,
            engine_version=row.engine_version,
            evidence_rows=row.evidence,
        )

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
