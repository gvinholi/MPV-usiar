from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from collector.application.internal_auth import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    AuditOutcome,
    BootstrapAdmin,
    BootstrapAlreadyCompletedError,
    InternalSession,
    LoginAttempt,
    PasswordHasher,
)
from collector.infra.database import SqlAlchemyInternalAuthRepository

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 10, 9, 15, tzinfo=UTC)


@pytest.fixture
def repository(migrated_engine, db_session):
    factory = sessionmaker(
        bind=migrated_engine, autoflush=False, expire_on_commit=False
    )
    return SqlAlchemyInternalAuthRepository(factory)


def bootstrap(repository, email: str = "Admin@Example.COM") -> UUID:
    return BootstrapAdmin(repository, PasswordHasher(), clock=lambda: NOW).execute(
        email,
        "senha de bootstrap muito forte",
    )


def test_catalog_contains_only_permissions_and_no_automatic_identity(
    db_session,
) -> None:
    assert set(
        db_session.execute(text("SELECT code FROM auth_permissions")).scalars()
    ) == {
        "dashboard:read",
        "reviews:write",
    }
    for table in (
        "auth_users",
        "auth_user_permissions",
        "auth_sessions",
        "auth_audit_events",
    ):
        assert (
            db_session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        )


def test_bootstrap_is_persistent_atomic_and_refuses_second_user(
    repository, db_session
) -> None:
    user_id = bootstrap(repository)

    user = repository.get_user_by_normalized_email("admin@example.com")
    assert user is not None
    assert user.id == user_id
    assert user.active
    assert repository.permissions_for_user(user_id) == ADMIN_PERMISSIONS
    audit = db_session.execute(
        text(
            "SELECT event_type, outcome, subject_user_id, request_id "
            "FROM auth_audit_events"
        )
    ).one()
    assert audit == ("BOOTSTRAP_ADMIN", "SUCCESS", user_id, None)

    with pytest.raises(BootstrapAlreadyCompletedError):
        bootstrap(repository, "second@example.com")
    assert repository.count_users() == 1


def test_normalized_email_is_unique_at_database_boundary(
    repository, db_session
) -> None:
    bootstrap(repository)
    original = db_session.execute(text("SELECT * FROM auth_users")).mappings().one()
    duplicate = dict(original)
    duplicate.update(id=uuid4(), email="other@example.com")

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO auth_users "
                "(id,email,normalized_email,display_name,password_hash,password_version,active,"
                "created_at,updated_at,last_login_at,disabled_at) VALUES "
                "(:id,:email,:normalized_email,:display_name,:password_hash,:password_version,:active,"
                ":created_at,:updated_at,:last_login_at,:disabled_at)"
            ),
            duplicate,
        )


def test_session_attempt_and_audit_persistence(repository) -> None:
    user_id = bootstrap(repository)
    session_id = uuid4()
    value = InternalSession(
        id=session_id,
        verifier_digest=b"v" * 32,
        csrf_digest=b"c" * 32,
        user_id=user_id,
        password_version=1,
        created_at=NOW,
        last_seen_at=NOW,
        idle_expires_at=NOW + timedelta(minutes=30),
        absolute_expires_at=NOW + timedelta(hours=8),
    )
    repository.create_session(value)
    assert repository.get_session(session_id) == value
    assert repository.revoke_session(session_id, NOW + timedelta(minutes=1), "logout")
    assert not repository.revoke_session(
        session_id, NOW + timedelta(minutes=2), "logout"
    )
    revoked = repository.get_session(session_id)
    assert revoked is not None and revoked.revoke_reason == "logout"

    attempt = LoginAttempt(
        key_digest=b"k" * 32,
        failure_count=1,
        window_started_at=NOW,
        last_failure_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        blocked_until=None,
    )
    repository.save_login_attempt(attempt)
    assert repository.get_login_attempt(attempt.key_digest) == attempt

    repository.append_audit_event(
        AuditEvent(
            id=uuid4(),
            event_type="SESSION_REVOKED",
            outcome=AuditOutcome.SUCCESS,
            subject_user_id=user_id,
            occurred_at=NOW,
            created_at=NOW,
        )
    )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO auth_sessions (id,verifier_digest,csrf_digest,user_id,password_version,created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES (gen_random_uuid(), decode(repeat('00',31),'hex'), decode(repeat('00',32),'hex'), gen_random_uuid(), 1, now(), now(), now()+interval '1 minute', now()+interval '1 hour')",
        "INSERT INTO auth_login_attempts (key_digest,failure_count,window_started_at,last_failure_at,created_at,updated_at) VALUES (decode(repeat('00',32),'hex'), -1, now(), now(), now(), now())",
        "INSERT INTO auth_audit_events (id,event_type,outcome,request_id,occurred_at,created_at) VALUES (gen_random_uuid(), 'bad-event', 'SUCCESS', 'safe', now(), now())",
    ],
)
def test_database_constraints_and_referential_integrity(
    db_session, statement: str
) -> None:
    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(text(statement))


def test_bootstrap_rolls_back_user_permissions_and_event_on_failure(
    repository,
    db_session,
) -> None:
    conflicting_event_id = UUID("00000000-0000-0000-0000-000000000099")
    db_session.execute(
        text(
            "INSERT INTO auth_audit_events "
            "(id,event_type,outcome,occurred_at,created_at) "
            "VALUES (:id,'PREEXISTING','SUCCESS',:now,:now)"
        ),
        {"id": conflicting_event_id, "now": NOW},
    )
    db_session.commit()
    ids = iter((UUID("00000000-0000-0000-0000-000000000098"), conflicting_event_id))
    service = BootstrapAdmin(
        repository,
        PasswordHasher(),
        clock=lambda: NOW,
        id_factory=lambda: next(ids),
    )

    with pytest.raises(IntegrityError):
        service.execute("admin@example.com", "senha de bootstrap muito forte")

    assert repository.count_users() == 0
    assert (
        db_session.execute(
            text("SELECT count(*) FROM auth_user_permissions")
        ).scalar_one()
        == 0
    )
    assert (
        db_session.execute(text("SELECT count(*) FROM auth_audit_events")).scalar_one()
        == 1
    )
