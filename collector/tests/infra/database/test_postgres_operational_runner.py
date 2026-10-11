"""Runner operacional contra PostgreSQL real."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from collector.application import (
    CollectionRequest,
    OperationalCollectionRunner,
    PersistCollection,
    PersistOperationalResolution,
    PersistScreening,
    usiar_v1,
)
from collector.application.human_review import (
    HumanReviewDecision,
    HumanReviewReason,
    HumanReviewStatus,
    RecordHumanReview,
    RecordHumanReviewCommand,
    ReviewerIdentity,
)
from collector.application.persistence.errors import PersistenceError
from collector.infra.database import (
    SqlAlchemyCollectionRepository,
    SqlAlchemyOperationalResolutionRepository,
    SqlAlchemyOperationalRunRepository,
    SqlAlchemyScreeningRepository,
)
from collector.infra.database.human_review_store import SqlAlchemyHumanReviewRepository
from tests.application.persistence.factories import collection_result, process

pytestmark = pytest.mark.postgres


class StubCollector:
    def __init__(self, result):
        self.result = result

    def collect(self, _request):
        return self.result


def _request():
    return CollectionRequest(date(2026, 10, 1), date(2026, 10, 1), (6,), uf="SP")


def _runner(factory, result):
    return OperationalCollectionRunner(
        StubCollector(result),
        PersistCollection(SqlAlchemyCollectionRepository(factory)),
        PersistScreening(SqlAlchemyScreeningRepository(factory)),
        PersistOperationalResolution(
            SqlAlchemyOperationalResolutionRepository(factory)
        ),
        SqlAlchemyOperationalRunRepository(factory),
    )


def test_runner_persists_pipeline_and_metrics(migrated_engine, db_session):
    factory = sessionmaker(
        bind=migrated_engine, autoflush=False, expire_on_commit=False
    )
    result = collection_result(
        process(
            "candidate",
            description="Manutenção preventiva de aparelhos de ar condicionado.",
        ),
        process(
            "pending",
            description="Manutenção com instalação de sistema de climatização.",
        ),
        process(
            "discarded",
            description="Fornecimento de peças de ar condicionado.",
        ),
    )

    summary = _runner(factory, result).run(_request(), usiar_v1())

    assert (summary.candidates, summary.pending, summary.discarded) == (1, 1, 1)
    counts = {
        table: db_session.scalar(text(f"SELECT count(*) FROM {table}"))
        for table in (
            "collection_rounds",
            "processes",
            "process_observations",
            "screening_evaluations",
            "operational_resolutions",
        )
    }
    assert counts == {
        "collection_rounds": 1,
        "processes": 3,
        "process_observations": 3,
        "screening_evaluations": 3,
        "operational_resolutions": 3,
    }
    row = db_session.execute(
        text(
            "SELECT status,candidates,pending,discarded "
            "FROM collection_rounds WHERE id=:id"
        ),
        {"id": summary.round_id},
    ).one()
    assert row == ("SUCCESS", 1, 1, 1)


def test_new_round_reuses_process_and_preserves_human_review(
    migrated_engine, db_session
):
    factory = sessionmaker(
        bind=migrated_engine, autoflush=False, expire_on_commit=False
    )
    first = collection_result(
        process(
            "same",
            description="Manutenção preventiva de ar condicionado.",
        )
    )
    first_summary = _runner(factory, first).run(_request(), usiar_v1())
    first_resolution_id = db_session.scalar(
        text(
            "SELECT id FROM operational_resolutions "
            "WHERE process_id=(SELECT process_id FROM process_observations "
            "WHERE round_id=:round_id)"
        ),
        {"round_id": first_summary.round_id},
    )
    review_repo = SqlAlchemyHumanReviewRepository(factory)
    review = RecordHumanReview(review_repo).execute(
        RecordHumanReviewCommand(
            operational_resolution_id=first_resolution_id,
            reviewer=ReviewerIdentity("runner-test"),
            decision=HumanReviewDecision.SELECTED,
            reason=HumanReviewReason.RELEVANT_SCOPE_CONFIRMED,
            idempotency_key=str(uuid4()),
        )
    )

    second = collection_result(
        process(
            "same",
            description="Manutenção preventiva de ar condicionado atualizada.",
        )
    )
    second_summary = _runner(factory, second).run(_request(), usiar_v1())

    assert first_summary.round_id != second_summary.round_id
    assert db_session.scalar(text("SELECT count(*) FROM processes")) == 1
    assert db_session.scalar(text("SELECT count(*) FROM process_observations")) == 2
    assert db_session.scalar(text("SELECT count(*) FROM human_reviews")) == 1
    reviews = review_repo.list_reviews_for_process(review.process_id, review.profile_id)
    assert [item.id for item in reviews] == [review.id]
    status = review_repo.review_status_for_process(review.process_id, review.profile_id)
    assert status is not None
    assert status.human_review_status is HumanReviewStatus.REVIEWED
    assert status.human_decision is HumanReviewDecision.SELECTED


def test_same_round_replay_is_idempotent_in_postgres(migrated_engine, db_session):
    factory = sessionmaker(
        bind=migrated_engine, autoflush=False, expire_on_commit=False
    )
    result = collection_result(
        process("same", description="Higienização de sistema de climatização.")
    )
    runner = _runner(factory, result)

    first = runner.run(_request(), usiar_v1())
    second = runner.run(_request(), usiar_v1())

    assert first.observations_created == 1
    assert second.observations_created == 0
    assert second.evaluations_created == 0
    assert second.resolutions_created == 0
    assert db_session.scalar(text("SELECT count(*) FROM collection_rounds")) == 1
    assert db_session.scalar(text("SELECT count(*) FROM process_observations")) == 1
    assert db_session.scalar(text("SELECT count(*) FROM screening_evaluations")) == 1
    assert db_session.scalar(text("SELECT count(*) FROM operational_resolutions")) == 1


def test_postgres_connection_failure_is_sanitized(migrated_engine):
    unavailable = create_engine(
        migrated_engine.url.set(database="usiar_commit25_missing_database"),
        connect_args={"connect_timeout": 2},
    )
    repository = SqlAlchemyOperationalRunRepository(
        sessionmaker(bind=unavailable, autoflush=False, expire_on_commit=False)
    )

    try:
        with pytest.raises(PersistenceError, match="falha ao consultar observações"):
            repository.list_round_observations(uuid4())
    finally:
        unavailable.dispose()
