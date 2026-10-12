"""Persistência da triagem contra PostgreSQL real."""

from __future__ import annotations

from dataclasses import replace
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from collector.application import (
    PersistCollection,
    PersistScreening,
    ScreeningEngine,
    usiar_v1,
    usiar_v2,
)
from collector.infra.database import SqlAlchemyScreeningRepository
from tests.application.persistence.factories import collection_result, process

pytestmark = pytest.mark.postgres


@pytest.fixture
def screening_service(migrated_engine, db_session: Session) -> PersistScreening:
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistScreening(SqlAlchemyScreeningRepository(factory))


def _persist_observation(
    persist_service: PersistCollection,
    db_session: Session,
    description: str,
    official_id: str = "123",
):
    snapshot = process(official_id, description=description)
    persist_service.persist(collection_result(snapshot))
    row = db_session.execute(
        text("SELECT id, process_id FROM process_observations")
    ).one()
    return snapshot, row[0], row[1]


def test_screening_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {
        "screening_profiles",
        "screening_evaluations",
        "screening_evidence",
    }.issubset(names)


def test_process_has_no_commercial_status_column(db_session: Session) -> None:
    columns = set(
        db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'processes'"
            )
        ).scalars()
    )
    assert columns == {"id", "created_at", "updated_at"}


def test_insert_usiar_v1_and_unique_code_version(
    screening_service: PersistScreening, db_session: Session
) -> None:
    screening_service.persist_profile(usiar_v1())
    screening_service.persist_profile(usiar_v1())
    count = db_session.execute(text("SELECT COUNT(*) FROM screening_profiles")).scalar_one()
    assert count == 1
    with pytest.raises(Exception):
        db_session.execute(
            text(
                "INSERT INTO screening_profiles "
                "(id, code, name, version, active, configuration, created_at) "
                "VALUES (gen_random_uuid(), 'USIAR', 'x', 'v1', true, '{}', now())"
            )
        )
        db_session.commit()
    db_session.rollback()


def test_insert_usiar_v2_preserves_contextual_configuration(
    screening_service: PersistScreening,
) -> None:
    first = screening_service.persist_profile(usiar_v2())
    second = screening_service.persist_profile(usiar_v2())

    assert first.id == second.id
    assert second.identity == "USIAR/v2"
    assert second.association_window_tokens == 1
    assert "refrigeração" in second.ambiguous_context_terms
    assert "ar condicionado veicular" in second.excluded_context_terms


def test_persist_evaluation_and_evidence(
    persist_service: PersistCollection,
    screening_service: PersistScreening,
    db_session: Session,
) -> None:
    snapshot, observation_id, process_id = _persist_observation(
        persist_service,
        db_session,
        "Manutenção preventiva de aparelhos de ar condicionado.",
    )
    profile = screening_service.persist_profile(usiar_v1())
    evaluation = ScreeningEngine().evaluate(
        profile,
        description=snapshot.description,
        process_id=process_id,
        observation_id=observation_id,
        profile_id=profile.id,
    )
    outcome = screening_service.persist_evaluation(evaluation)
    assert outcome.created is True
    states = db_session.execute(text("SELECT state FROM screening_evaluations")).all()
    assert states == [("CANDIDATE",)]
    evidence_count = db_session.execute(
        text("SELECT COUNT(*) FROM screening_evidence")
    ).scalar_one()
    assert evidence_count >= 2


def test_same_observation_same_profile_does_not_duplicate(
    persist_service: PersistCollection,
    screening_service: PersistScreening,
    db_session: Session,
) -> None:
    snapshot, observation_id, process_id = _persist_observation(
        persist_service, db_session, "Manutenção preventiva de chillers."
    )
    profile = screening_service.persist_profile(usiar_v1())
    evaluation = ScreeningEngine().evaluate(
        profile,
        description=snapshot.description,
        process_id=process_id,
        observation_id=observation_id,
        profile_id=profile.id,
    )
    screening_service.persist_evaluation(evaluation)
    screening_service.persist_evaluation(evaluation)
    assert db_session.execute(text("SELECT COUNT(*) FROM screening_evaluations")).scalar_one() == 1


def test_same_observation_new_version_keeps_history(
    persist_service: PersistCollection,
    screening_service: PersistScreening,
    db_session: Session,
) -> None:
    snapshot, observation_id, process_id = _persist_observation(
        persist_service, db_session, "Manutenção preventiva de chillers."
    )
    v1 = screening_service.persist_profile(usiar_v1())
    v2 = screening_service.persist_profile(usiar_v2())
    first = ScreeningEngine().evaluate(
        v1,
        description=snapshot.description,
        process_id=process_id,
        observation_id=observation_id,
        profile_id=v1.id,
    )
    second = replace(
        ScreeningEngine().evaluate(
            v2,
            description=snapshot.description,
            process_id=process_id,
            observation_id=observation_id,
            profile_id=v2.id,
        ),
        profile_version="v2",
    )
    screening_service.persist_evaluation(first)
    screening_service.persist_evaluation(second)
    versions = set(
        db_session.execute(
            text(
                "SELECT p.version FROM screening_evaluations e "
                "JOIN screening_profiles p ON p.id = e.profile_id"
            )
        ).scalars()
    )
    assert versions == {"v1", "v2"}
    assert db_session.execute(text("SELECT COUNT(*) FROM processes")).scalar_one() == 1
