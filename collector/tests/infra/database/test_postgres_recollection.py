"""Coletas repetidas: a resolução vigente sobrevive a reobservações equivalentes."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from collector.application import PersistCollection, usiar_v1
from collector.application.human_review import (
    HumanReviewDecision,
    HumanReviewReason,
    HumanReviewStatus,
    RecordHumanReview,
    RecordHumanReviewCommand,
    ReviewerIdentity,
)
from collector.application.read_model import (
    DashboardQueries,
    OpportunityFilters,
    ProfileScope,
)
from collector.infra.database import SqlAlchemyCollectionRepository
from collector.infra.database.human_review_store import SqlAlchemyHumanReviewRepository
from collector.infra.database.read_model_store import SqlAlchemyReadModelStore
from tests.application.persistence.factories import STARTED, collection_result, process

from .test_postgres_operational_runner import _request, _runner

pytestmark = pytest.mark.postgres

TEXTS = {
    "REC-CANDIDATE": "Manutenção preventiva de aparelhos de ar condicionado.",
    "REC-PENDING": "Manutenção com instalação de sistema de climatização.",
    "REC-DISCARDED": "Fornecimento de peças de ar condicionado.",
}
ALL_STATES = OpportunityFilters(operational_state=("CANDIDATE", "PENDING", "DISCARDED"))


def _collect(factory, round_number: int, texts: dict[str, str]):
    captured = STARTED + timedelta(hours=6 * round_number)
    result = collection_result(
        *(process(official_id, description=description, last_captured_at=captured)
          for official_id, description in texts.items()),
        round_id=uuid4(),
        started_at=captured,
        ended_at=captured + timedelta(minutes=5),
    )
    return _runner(factory, result).run(_request(), usiar_v1())


def _visible(queries, scope):
    page = queries.list_opportunities(scope, ALL_STATES)
    return {item.official_id: item for item in page.items}


def _count(db_session, table: str) -> int:
    return db_session.scalar(text(f"SELECT count(*) FROM {table}"))


@pytest.fixture
def pipeline(migrated_engine, db_session):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    queries = DashboardQueries(SqlAlchemyReadModelStore(factory))
    return factory, queries, SqlAlchemyHumanReviewRepository(factory)


def test_three_equivalent_collections_keep_state_reviews_and_no_duplicates(pipeline, db_session):
    factory, queries, reviews = pipeline
    _collect(factory, 0, TEXTS)
    profile_id = db_session.scalar(text("SELECT id FROM screening_profiles"))
    scope = ProfileScope(profile_id=profile_id)
    first = _visible(queries, scope)
    expected_states = {key: item.operational_state for key, item in first.items()}
    assert sorted(expected_states.values()) == ["CANDIDATE", "DISCARDED", "PENDING"]

    reviewed = first["REC-CANDIDATE"]
    review = RecordHumanReview(reviews).execute(
        RecordHumanReviewCommand(
            operational_resolution_id=reviewed.operational_resolution_id,
            reviewer=ReviewerIdentity("recollection-test"),
            decision=HumanReviewDecision.SELECTED,
            reason=HumanReviewReason.RELEVANT_SCOPE_CONFIRMED,
            idempotency_key=str(uuid4()),
        )
    )

    for round_number in (1, 2):
        _collect(factory, round_number, TEXTS)
        visible = _visible(queries, scope)
        assert set(visible) == set(TEXTS), round_number
        assert {key: item.operational_state for key, item in visible.items()} == expected_states
        candidate = visible["REC-CANDIDATE"]
        assert candidate.operational_resolution_id == reviewed.operational_resolution_id
        assert candidate.human_review_status is HumanReviewStatus.REVIEWED
        assert candidate.human_decision is HumanReviewDecision.SELECTED
        assert visible["REC-PENDING"].human_review_status is HumanReviewStatus.UNREVIEWED

    status = reviews.review_status_for_process(review.process_id, review.profile_id)
    assert status.human_review_status is HumanReviewStatus.REVIEWED
    assert _count(db_session, "collection_rounds") == 3
    assert _count(db_session, "processes") == 3
    assert _count(db_session, "process_observations") == 9
    assert _count(db_session, "screening_evaluations") == 9
    assert _count(db_session, "operational_resolutions") == 3
    assert _count(db_session, "human_reviews") == 1


def test_real_reclassification_is_reflected_and_marks_review_stale(pipeline, db_session):
    factory, queries, reviews = pipeline
    _collect(factory, 0, TEXTS)
    scope = ProfileScope(profile_id=db_session.scalar(text("SELECT id FROM screening_profiles")))
    original = _visible(queries, scope)["REC-CANDIDATE"]
    RecordHumanReview(reviews).execute(
        RecordHumanReviewCommand(
            operational_resolution_id=original.operational_resolution_id,
            reviewer=ReviewerIdentity("recollection-test"),
            decision=HumanReviewDecision.SELECTED,
            reason=HumanReviewReason.RELEVANT_SCOPE_CONFIRMED,
            idempotency_key=str(uuid4()),
        )
    )
    _collect(factory, 1, TEXTS)

    changed = dict(TEXTS, **{"REC-CANDIDATE": TEXTS["REC-DISCARDED"]})
    _collect(factory, 2, changed)
    visible = _visible(queries, scope)
    item = visible["REC-CANDIDATE"]
    assert item.operational_state == "DISCARDED"
    assert item.operational_resolution_id != original.operational_resolution_id
    assert item.human_review_status is HumanReviewStatus.STALE
    assert visible["REC-PENDING"].operational_state == "PENDING"
    assert _count(db_session, "operational_resolutions") == 4

    # Voltar ao conteúdo original reaproveita a resolução original (mesmo fingerprint).
    _collect(factory, 3, TEXTS)
    item = _visible(queries, scope)["REC-CANDIDATE"]
    assert item.operational_state == "CANDIDATE"
    assert item.operational_resolution_id == original.operational_resolution_id
    assert _count(db_session, "operational_resolutions") == 4


def test_latest_observation_without_evaluation_still_has_no_resolution(pipeline, db_session):
    factory, queries, _ = pipeline
    _collect(factory, 0, TEXTS)
    scope = ProfileScope(profile_id=db_session.scalar(text("SELECT id FROM screening_profiles")))
    # Rodada persistida sem triagem: a captura mais nova não tem avaliação do perfil.
    captured = STARTED + timedelta(days=1)
    PersistCollection(SqlAlchemyCollectionRepository(factory)).persist(
        collection_result(
            process("REC-PENDING", description=TEXTS["REC-PENDING"], last_captured_at=captured),
            round_id=uuid4(), started_at=captured, ended_at=captured + timedelta(minutes=5),
        )
    )
    unfiltered = {item.official_id: item for item in queries.list_opportunities(scope).items}
    assert unfiltered["REC-PENDING"].operational_state is None
    assert "REC-PENDING" not in _visible(queries, scope)
    assert _visible(queries, scope)["REC-CANDIDATE"].operational_state == "CANDIDATE"
