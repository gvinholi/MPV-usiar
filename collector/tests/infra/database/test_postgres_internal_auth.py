from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from argon2 import PasswordHasher as RawArgon2PasswordHasher
from argon2 import Type
from collector.api.app import create_app
from collector.api.settings import ApiSettings
from collector.application.internal_auth import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    AuditOutcome,
    BootstrapAdmin,
    BootstrapAlreadyCompletedError,
    InternalLoginService,
    InternalSession,
    InternalSessionService,
    InvalidCsrfTokenError,
    InvalidInternalSessionError,
    LoginAttempt,
    LoginRatePolicy,
    PasswordHasher,
    RateLimitKeyDeriver,
    generate_session_secrets,
    parse_session_token,
)
from collector.infra.database import SqlAlchemyInternalAuthRepository
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 10, 9, 15, tzinfo=UTC)
RATE_KEY = base64.urlsafe_b64encode(b"p" * 32).rstrip(b"=").decode()


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


def test_real_login_session_permissions_password_version_and_logout(
    repository, db_session
) -> None:
    user_id = bootstrap(repository)
    login = InternalLoginService(
        repository, PasswordHasher(), RateLimitKeyDeriver(RATE_KEY)
    )
    sessions = InternalSessionService(repository)
    created = login.login(
        "admin@example.com",
        "senha de bootstrap muito forte",
        request_id="pg-login",
        now=NOW + timedelta(minutes=1),
    )

    identity = sessions.authenticate(
        created.session_token, now=NOW + timedelta(minutes=2)
    )
    assert identity.user_id == user_id
    assert identity.permissions == frozenset({"dashboard:read", "reviews:write"})
    assert db_session.execute(
        text("SELECT last_login_at FROM auth_users WHERE id=:id"), {"id": user_id}
    ).scalar_one() == NOW + timedelta(minutes=1)

    db_session.execute(
        text(
            "DELETE FROM auth_user_permissions "
            "WHERE user_id=:id AND permission_code='reviews:write'"
        ),
        {"id": user_id},
    )
    db_session.commit()
    changed = sessions.authenticate(
        created.session_token, now=NOW + timedelta(minutes=3)
    )
    assert changed.permissions == frozenset({"dashboard:read"})

    sessions.logout(
        created.session_token,
        created.csrf_token,
        request_id="pg-logout",
        now=NOW + timedelta(minutes=4),
    )
    sessions.logout(
        created.session_token,
        created.csrf_token,
        request_id="pg-logout-retry",
        now=NOW + timedelta(minutes=5),
    )
    with pytest.raises(InvalidInternalSessionError):
        sessions.authenticate(created.session_token, now=NOW + timedelta(minutes=5))
    assert (
        db_session.execute(
            text(
                "SELECT count(*) FROM auth_audit_events WHERE event_type='SESSION_REVOKED'"
            )
        ).scalar_one()
        == 1
    )

    second = login.login(
        "admin@example.com",
        "senha de bootstrap muito forte",
        request_id="pg-login-2",
        now=NOW + timedelta(minutes=6),
    )
    db_session.execute(
        text(
            "UPDATE auth_users SET password_version=password_version+1, "
            "updated_at=:now WHERE id=:id"
        ),
        {"id": user_id, "now": NOW + timedelta(minutes=7)},
    )
    db_session.commit()
    with pytest.raises(InvalidInternalSessionError):
        sessions.authenticate(second.session_token, now=NOW + timedelta(minutes=8))


def test_identifier_rate_limit_is_atomic_under_real_concurrency(repository) -> None:
    deriver = RateLimitKeyDeriver(RATE_KEY)
    identifier = deriver.identifier("admin@example.com")
    global_key = deriver.global_key()
    policy = LoginRatePolicy()

    def reserve(_index):
        return repository.reserve_login_attempt(
            identifier, global_key, NOW, policy
        ).allowed

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(10)))
    assert results.count(True) == 5
    assert results.count(False) == 5


def test_global_rate_limit_is_shared_across_identifiers(repository) -> None:
    deriver = RateLimitKeyDeriver(RATE_KEY)
    policy = LoginRatePolicy()
    allowed = [
        repository.reserve_login_attempt(
            deriver.identifier(f"user-{index}@example.com"),
            deriver.global_key(),
            NOW,
            policy,
        ).allowed
        for index in range(61)
    ]
    assert allowed[:60] == [True] * 60
    assert allowed[60] is False


def test_session_expiration_touch_interval_and_valid_csrf_mismatch(
    repository, db_session
) -> None:
    bootstrap(repository)
    login = InternalLoginService(
        repository, PasswordHasher(), RateLimitKeyDeriver(RATE_KEY)
    )
    sessions = InternalSessionService(repository)
    created = login.login(
        "admin@example.com",
        "senha de bootstrap muito forte",
        request_id=None,
        now=NOW,
    )
    session_id, _ = parse_session_token(created.session_token)

    sessions.authenticate(created.session_token, now=NOW + timedelta(minutes=4))
    assert (
        db_session.execute(
            text("SELECT last_seen_at FROM auth_sessions WHERE id=:id"),
            {"id": session_id},
        ).scalar_one()
        == NOW
    )
    sessions.authenticate(created.session_token, now=NOW + timedelta(minutes=6))
    touched = db_session.execute(
        text("SELECT last_seen_at, idle_expires_at FROM auth_sessions WHERE id=:id"),
        {"id": session_id},
    ).one()
    assert touched == (
        NOW + timedelta(minutes=6),
        NOW + timedelta(minutes=36),
    )

    wrong_csrf = generate_session_secrets().csrf_token
    with pytest.raises(InvalidCsrfTokenError):
        sessions.logout(
            created.session_token,
            wrong_csrf,
            request_id=None,
            now=NOW + timedelta(minutes=7),
        )
    with pytest.raises(InvalidInternalSessionError):
        sessions.authenticate(created.session_token, now=NOW + timedelta(hours=8))


def test_login_rehash_is_atomic_and_invalidates_older_password_version(
    repository, db_session
) -> None:
    user_id = bootstrap(repository)
    old_hash = RawArgon2PasswordHasher(
        time_cost=1,
        memory_cost=19 * 1024,
        parallelism=1,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    ).hash("senha de bootstrap muito forte")
    db_session.execute(
        text("UPDATE auth_users SET password_hash=:hash WHERE id=:id"),
        {"hash": old_hash, "id": user_id},
    )
    db_session.commit()
    login = InternalLoginService(
        repository, PasswordHasher(), RateLimitKeyDeriver(RATE_KEY)
    )
    created = login.login(
        "admin@example.com",
        "senha de bootstrap muito forte",
        request_id="rehash",
        now=NOW + timedelta(minutes=1),
    )
    password_hash, password_version = db_session.execute(
        text("SELECT password_hash, password_version FROM auth_users WHERE id=:id"),
        {"id": user_id},
    ).one()
    assert password_version == 2
    assert password_hash != old_hash
    assert PasswordHasher().verify(password_hash, "senha de bootstrap muito forte")
    assert (
        InternalSessionService(repository)
        .authenticate(created.session_token, now=NOW + timedelta(minutes=2))
        .user_id
        == user_id
    )


def test_internal_http_login_authorization_logout_and_replay(
    migrated_engine, db_session
) -> None:
    factory = sessionmaker(
        bind=migrated_engine, autoflush=False, expire_on_commit=False
    )
    repository = SqlAlchemyInternalAuthRepository(factory)
    bootstrap(repository)
    api = TestClient(
        create_app(
            queries=object(),
            session_factory=factory,
            settings=ApiSettings(
                auth_mode="internal",
                database_url="postgresql-configured-server-side",
                internal_auth_rate_limit_key=RATE_KEY,
            ),
        ),
        raise_server_exceptions=False,
    )
    login = api.post(
        "/api/v1/auth/session",
        json={
            "email": "admin@example.com",
            "password": "senha de bootstrap muito forte",
        },
    )
    assert login.status_code == 201
    body = login.json()
    authorization = {"Authorization": f"Bearer {body['session_token']}"}
    assert (
        api.get(
            "/ready", headers={"Authorization": "Bearer header.payload.signature"}
        ).status_code
        == 401
    )
    assert api.get("/ready", headers=authorization).status_code == 200
    logout = api.delete(
        "/api/v1/auth/session",
        headers={**authorization, "X-CSRF-Token": body["csrf_token"]},
    )
    assert logout.status_code == 204
    replay = api.get("/ready", headers=authorization)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "INVALID_CREDENTIALS"
