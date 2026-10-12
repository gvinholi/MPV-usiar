"""Real PostgreSQL workflow, constraints, concurrency, and controlled demos."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from collector.application import (
    OperationalResolver, PersistOperationalResolution, PersistScreening,
    ScreeningEngine, usiar_v1, usiar_v2, EvaluateDocumentScreening, PersistDocumentScreening,
)
from collector.application.human_review import (
    HumanReviewDecision as D, HumanReviewReason as R, HumanReviewStatus as S,
    RecordHumanReview, RecordHumanReviewCommand, ReviewerIdentity, ReviewQueue as Q,
    IdempotencyConflictError, StaleOperationalResolutionError,
)
from collector.api.app import create_app
from collector.api.settings import ApiSettings
from collector.api.security import AuthenticatedPrincipal
from collector.infra.database import (
    SqlAlchemyScreeningRepository, SqlAlchemyOperationalResolutionRepository,
    SqlAlchemyDocumentScreeningRepository,
)
from collector.infra.database.human_review_store import SqlAlchemyHumanReviewRepository, human_reviews
from tests.application.persistence.factories import process, collection_result
from tests.infra.database.test_postgres_resolution import _seed

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


@pytest.fixture
def setup(migrated_engine, db_session, persist_service):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    snapshot = process("HUMAN-CONTROLLED", description="Manutencao preventiva de aparelhos de ar condicionado.")
    persist_service.persist(collection_result(snapshot))
    screening = PersistScreening(SqlAlchemyScreeningRepository(factory))
    profile = screening.persist_profile(usiar_v1())
    observation = db_session.execute(text("SELECT id FROM process_observations")).scalar_one()
    evaluation = ScreeningEngine().evaluate(profile, description=snapshot.description,
        process_id=snapshot.id, observation_id=observation, profile_id=profile.id)
    screening.persist_evaluation(evaluation)
    resolution = replace(OperationalResolver().resolve(evaluation, None), resolved_at=NOW)
    operational = PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factory))
    operational.persist(resolution)
    repo = SqlAlchemyHumanReviewRepository(factory)
    return factory, repo, operational, resolution


def cmd(resolution, **kwargs):
    fields = dict(operational_resolution_id=resolution.id, reviewer=ReviewerIdentity("gabriel"),
                  decision=D.SELECTED, reason=R.RELEVANT_SCOPE_CONFIRMED,
                  idempotency_key=str(uuid4()))
    fields.update(kwargs)
    return RecordHumanReviewCommand(**fields)


def current(repo, resolution):
    return repo.review_status_for_process(resolution.process_id, resolution.profile_id)


def next_resolution(operational, resolution, **kwargs):
    fields = dict(id=uuid4(), resolved_at=resolution.resolved_at + timedelta(minutes=1),
                  resolution_fingerprint=uuid4().hex)
    fields.update(kwargs)
    result = replace(resolution, **fields)
    operational.persist(result)
    return result


class AuthorizedReviewer:
    def authenticate(self, _token):
        return AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="reviewer-123",
            display_name="Revisor Autorizado",
            permissions=frozenset({"reviews:write"}),
        )


def review_client(factory):
    return TestClient(
        create_app(
            queries=object(),
            session_factory=factory,
            settings=ApiSettings(auth_mode="oidc"),
            authenticator=AuthorizedReviewer(),
        )
    )


def review_payload(resolution, **overrides):
    payload = {
        "operational_resolution_id": str(resolution.id),
        "decision": "SELECTED",
        "reason": "RELEVANT_SCOPE_CONFIRMED",
        "comment": "Escopo confirmado na revisao.",
        "idempotency_key": str(uuid4()),
        "allow_stale": False,
    }
    payload.update(overrides)
    return payload


def previous_layers(session):
    return {table: session.execute(text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY id")).scalars().all()
            for table in ("processes", "screening_evaluations", "document_screening_evaluations", "operational_resolutions")}


def test_selected_append_only_idempotency_and_queues(setup, db_session):
    factory, repo, operational, resolution = setup
    service = RecordHumanReview(repo, clock=lambda: NOW)
    before = previous_layers(db_session)
    assert current(repo, resolution).human_review_status == S.UNREVIEWED
    assert len(repo.list_queue(Q.NEEDS_REVIEW)) == 1
    request = cmd(resolution, idempotency_key="commit15-demo-001")
    first = service.execute(request)
    assert service.execute(request).id == first.id
    with pytest.raises(IdempotencyConflictError):
        service.execute(replace(request, decision=D.DISCARDED, reason=R.COMMERCIAL_DECISION))
    assert len(repo.list_queue(Q.SELECTED)) == 1
    assert current(repo, resolution).operational_state == "CANDIDATE"
    assert first.latest_resolution_id_at_decision == resolution.id
    assert first.was_stale_at_decision is False
    for decision, reason, queue in ((D.PENDING, R.NEEDS_DOCUMENT_REVIEW, Q.HUMAN_PENDING),
                                   (D.DISCARDED, R.COMMERCIAL_DECISION, Q.HUMAN_DISCARDED)):
        last = service.execute(cmd(resolution, decision=decision, reason=reason))
        assert repo.latest_review_for_resolution(resolution.id).id == last.id
        assert len(repo.list_queue(queue)) == 1
    history = repo.list_reviews_for_process(resolution.process_id, resolution.profile_id)
    assert len(history) == 3
    assert history[-1].id == first.id
    assert previous_layers(db_session) == before
    summary = repo.summary()
    assert (summary.current_resolutions, summary.reviewed, summary.human_discarded, summary.reviews_total) == (1, 1, 1, 3)
    assert summary.needs_review == 0
    print(f"SELECTED demo: review={first.id}, resolution={resolution.id}, reviewer=gabriel, operational=CANDIDATE, human=SELECTED, previous_layers_unchanged=True")
    print(f"Idempotency demo: same_id={first.id}, conflicting_payload=rejected; counts={summary}")


def test_stale_override_retry_and_new_review(setup):
    _, repo, operational, a = setup
    service = RecordHumanReview(repo)
    request = cmd(a)
    first = service.execute(request)
    b = next_resolution(operational, a)
    assert current(repo, a).human_review_status == S.STALE
    assert current(repo, a).human_decision is None
    assert len(repo.list_queue(Q.STALE_REVIEW)) == 1
    assert len(repo.list_queue(Q.NEEDS_REVIEW)) == 1
    assert service.execute(request).id == first.id  # retry survives later resolution
    with pytest.raises(StaleOperationalResolutionError) as error:
        service.execute(cmd(a))
    assert error.value.latest_resolution_id == b.id
    stale = service.execute(cmd(a, allow_stale=True))
    assert stale.was_stale_at_decision
    assert stale.latest_resolution_id_at_decision == b.id
    assert current(repo, a).human_review_status == S.STALE
    fresh = service.execute(cmd(b))
    assert current(repo, a).human_review_status == S.REVIEWED
    # A later override on A cannot hide a valid review of B.
    service.execute(cmd(a, allow_stale=True))
    assert current(repo, a).human_review_status == S.REVIEWED
    assert repo.latest_review_for_resolution(b.id).id == fresh.id
    assert repo.summary().stale_overrides_total == 2
    print(f"Stale demo: A={a.id}, B={b.id}, reject={error.value}, override={stale.id}, stale=True, latest_status=REVIEWED")


def test_automatic_discarded_excluded_by_default(setup):
    from collector.domain import ScreeningStatus
    _, repo, operational, a = setup
    discarded = next_resolution(operational, a, state=ScreeningStatus.DISCARDED)
    assert repo.list_queue(Q.NEEDS_REVIEW) == ()
    assert len(repo.list_queue(Q.NEEDS_REVIEW, include_operational_discarded=True)) == 1
    assert current(repo, discarded).human_review_status == S.UNREVIEWED
    assert repo.summary().reviews_total == 0
    RecordHumanReview(repo).execute(cmd(discarded))
    assert len(repo.list_queue(Q.SELECTED)) == 1


def test_resolution_committed_between_check_and_insert_is_visible_as_stale(setup):
    _, repo, operational, a = setup
    def racing_clock():
        next_resolution(operational, a)
        return NOW
    review = RecordHumanReview(repo, clock=racing_clock).execute(cmd(a))
    # Honest READ COMMITTED limitation: audit reflects the checked snapshot;
    # current status immediately detects the newer resolution.
    assert review.was_stale_at_decision is False
    assert review.latest_resolution_id_at_decision == a.id
    assert current(repo, a).human_review_status == S.STALE


def test_profile_isolation(setup):
    factory, repo, operational, a = setup
    screening = PersistScreening(SqlAlchemyScreeningRepository(factory))
    profile = screening.persist_profile(usiar_v2())
    with factory() as session:
        observation = session.execute(text("SELECT id FROM process_observations WHERE process_id = :id"), {"id": a.process_id}).scalar_one()
    initial = ScreeningEngine().evaluate(profile, description="Manutencao preventiva de aparelhos de ar condicionado.",
        process_id=a.process_id, observation_id=observation, profile_id=profile.id)
    screening.persist_evaluation(initial)
    b = OperationalResolver().resolve(initial, None)
    operational.persist(b)
    RecordHumanReview(repo).execute(cmd(a))
    assert current(repo, a).human_review_status == S.REVIEWED
    assert current(repo, b).human_review_status == S.UNREVIEWED
    assert len(repo.list_queue(Q.NEEDS_REVIEW, profile_id=profile.id)) == 1
    assert len(repo.list_queue(include_operational_discarded=True)) == 2
    assert repo.summary(profile_id=profile.id).reviews_total == 0


def test_valid_reason_matrix_in_postgres(setup):
    from collector.application.human_review.models import ALLOWED_REASONS
    _, repo, _, resolution = setup
    service = RecordHumanReview(repo)
    for decision, reasons in ALLOWED_REASONS.items():
        for reason in reasons:
            review = service.execute(cmd(resolution, decision=decision, reason=reason,
                                         comment="explicit reason" if reason == R.OTHER else None))
            assert review.command.reason == reason
    assert repo.summary().reviews_total == sum(map(len, ALLOWED_REASONS.values()))


def test_review_timestamp_precedes_insertion_sequence(setup):
    _, repo, _, resolution = setup
    selected = RecordHumanReview(repo, clock=lambda: NOW).execute(cmd(resolution))
    RecordHumanReview(repo, clock=lambda: NOW - timedelta(seconds=1)).execute(
        cmd(resolution, decision=D.DISCARDED, reason=R.COMMERCIAL_DECISION))
    assert repo.latest_review_for_resolution(resolution.id).id == selected.id


def test_missing_resolution_does_not_write(setup):
    _, repo, _, resolution = setup
    with pytest.raises(ValueError, match="not found"):
        RecordHumanReview(repo).execute(replace(cmd(resolution), operational_resolution_id=uuid4()))
    assert repo.summary().reviews_total == 0


@pytest.mark.parametrize("change", [
    {"decision": "CONFIRMED"}, {"decision": "CANDIDATE"}, {"reason_code": "OUT_OF_SCOPE"},
    {"decision": "PENDING", "reason_code": "OTHER", "comment": None},
    {"decision": "PENDING", "reason_code": "OTHER", "comment": "\n\t"},
    {"comment": "x" * 4001}, {"reviewer_id": "\n\t"}, {"idempotency_key": " "},
    {"operational_resolution_id": uuid4()}, {"latest_resolution_id_at_decision": uuid4()},
    {"resolution_fingerprint": "wrong"}, {"operational_state_snapshot": "PENDING"},
    {"was_stale_at_decision": True},
])
def test_database_constraints(setup, change):
    factory, repo, _, resolution = setup
    RecordHumanReview(repo).execute(cmd(resolution))
    with factory() as session:
        data = dict(session.execute(select(human_reviews)).mappings().one())
    data.pop("sequence")
    data.update(id=uuid4(), idempotency_key=str(uuid4()))
    data.update(change)
    with pytest.raises(DBAPIError):
        with factory.begin() as session:
            session.execute(human_reviews.insert().values(**data))


@pytest.mark.parametrize("statement", ["UPDATE human_reviews SET comment = 'changed'", "DELETE FROM human_reviews"])
def test_database_rejects_mutation(setup, statement):
    factory, repo, _, resolution = setup
    RecordHumanReview(repo).execute(cmd(resolution))
    with pytest.raises(DBAPIError, match="append-only"):
        with factory.begin() as session:
            session.execute(text(statement))
    assert repo.summary().reviews_total == 1


@pytest.mark.parametrize("conflict", [False, True])
def test_concurrent_idempotency(setup, conflict):
    factory, repo, _, resolution = setup
    barrier = Barrier(2)
    request = cmd(resolution)
    other = replace(request, comment="different") if conflict else request
    def run(command):
        barrier.wait(timeout=10)
        try:
            return RecordHumanReview(SqlAlchemyHumanReviewRepository(factory)).execute(command)
        except IdempotencyConflictError as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, c) for c in (request, other)]
        results = [f.result(timeout=20) for f in futures]
    if conflict:
        assert sum(isinstance(x, IdempotencyConflictError) for x in results) == 1
    else:
        assert results[0].id == results[1].id
    assert repo.summary().reviews_total == 1


def test_authenticated_review_http_persists_auditable_identity_and_is_idempotent(setup):
    factory, repo, _, resolution = setup
    client = review_client(factory)
    payload = review_payload(resolution, idempotency_key="http-postgres-idempotent")
    headers = {"Authorization": "Bearer test-token"}

    first = client.post("/api/v1/reviews", json=payload, headers=headers)
    retry = client.post("/api/v1/reviews", json=payload, headers=headers)

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["review_id"] == first.json()["review_id"]
    stored = repo.latest_review_for_resolution(resolution.id)
    assert stored is not None
    assert stored.id == UUID(first.json()["review_id"])
    assert stored.reviewer.reviewer_id == "oidc:22:https://issuer.examplereviewer-123"
    assert stored.reviewer.display_name == "Revisor Autorizado"
    assert stored.was_stale_at_decision is False
    assert repo.summary().reviews_total == 1

    conflict = client.post(
        "/api/v1/reviews",
        json={**payload, "comment": "Outro conteudo."},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert repo.summary().reviews_total == 1


def test_authenticated_review_http_handles_missing_and_stale_resolution(setup):
    factory, repo, operational, resolution = setup
    client = review_client(factory)
    headers = {"Authorization": "Bearer test-token"}

    missing = client.post(
        "/api/v1/reviews",
        json=review_payload(resolution, operational_resolution_id=str(uuid4())),
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "OPERATIONAL_RESOLUTION_NOT_FOUND"

    latest = next_resolution(operational, resolution)
    stale_payload = review_payload(resolution, idempotency_key="http-postgres-stale")
    blocked = client.post("/api/v1/reviews", json=stale_payload, headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "STALE_OPERATIONAL_RESOLUTION"

    allowed = client.post(
        "/api/v1/reviews",
        json={**stale_payload, "allow_stale": True, "idempotency_key": "http-postgres-stale-allowed"},
        headers=headers,
    )
    assert allowed.status_code == 201
    assert allowed.json()["was_stale_at_decision"] is True
    assert allowed.json()["latest_resolution_id_at_decision"] == str(latest.id)
    stored = repo.latest_review_for_resolution(resolution.id)
    assert stored is not None
    assert stored.was_stale_at_decision is True
    assert stored.latest_resolution_id_at_decision == latest.id


def test_controlled_3341_demo(migrated_engine, db_session, persist_service, tmp_path):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    # Controlled persisted fixture, not a claim about live PNCP/Commit 14 data.
    snapshot = _seed(factory, persist_service, tmp_path, official_id="COMMIT15-CONTROLLED-3341",
        sequential=3341, description="Manutencao e fornecimento de aparelhos de ar condicionado.",
        page_text="Regras para apresentacao da proposta.")
    screening = PersistScreening(SqlAlchemyScreeningRepository(factory))
    profile = screening.persist_profile(usiar_v1())
    observation = db_session.execute(text("SELECT id FROM process_observations")).scalar_one()
    initial = ScreeningEngine().evaluate(profile, description=snapshot.description,
        process_id=snapshot.id, observation_id=observation, profile_id=profile.id)
    screening.persist_evaluation(initial)
    document = EvaluateDocumentScreening(SqlAlchemyDocumentScreeningRepository(factory)).evaluate_process(snapshot.id, profile)
    PersistDocumentScreening(SqlAlchemyDocumentScreeningRepository(factory), SqlAlchemyScreeningRepository(factory)).persist_evaluation(document)
    resolution = OperationalResolver().resolve(initial, document)
    PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factory)).persist(resolution)
    assert resolution.state.value == "PENDING"
    assert resolution.reason_code.value == "DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE"
    before = previous_layers(db_session)
    repo = SqlAlchemyHumanReviewRepository(factory)
    review = RecordHumanReview(repo).execute(cmd(resolution, decision=D.PENDING, reason=R.NEEDS_DOCUMENT_REVIEW,
        comment="Descrição do PNCP não foi confirmada pelos documentos analisados."))
    assert current(repo, resolution).human_review_status == S.REVIEWED
    assert review.was_stale_at_decision is False
    assert before == previous_layers(db_session)
    print(f"3341 controlled: review={review.id}, resolution={resolution.id}, reviewer=gabriel, decision=PENDING, reason=NEEDS_DOCUMENT_REVIEW, status=REVIEWED, stale=False")
    print("DB counts:", {table: db_session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
          for table in ("processes", "screening_evaluations", "document_screening_evaluations", "operational_resolutions", "human_reviews")})
