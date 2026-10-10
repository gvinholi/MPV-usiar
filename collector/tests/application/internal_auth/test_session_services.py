from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Lock
from uuid import UUID, uuid4

import pytest
from collector.application.internal_auth import (
    AuditEvent,
    AuthenticatedInternalSession,
    AuthenticationCapacityError,
    AuthenticationRateLimitedError,
    InternalLoginService,
    InternalSessionService,
    InternalUser,
    InvalidCredentialsError,
    InvalidCsrfTokenError,
    InvalidInternalSessionError,
    LoginAttemptReservation,
    PasswordHasher,
    RateLimitKeyDeriver,
    SessionRevocationResult,
    generate_session_secrets,
    parse_csrf_token,
    parse_session_token,
)

NOW = datetime(2026, 10, 9, 16, tzinfo=UTC)
PASSWORD = "uma senha longa e segura"
RATE_KEY = base64.urlsafe_b64encode(b"r" * 32).rstrip(b"=").decode()


class Repository:
    def __init__(self, user: InternalUser | None = None) -> None:
        self.user = user
        self.reservation = LoginAttemptReservation(True)
        self.failures: list[AuditEvent] = []
        self.completed = []
        self.identity = None
        self.revocation = SessionRevocationResult.REVOKED

    def reserve_login_attempt(self, *args):
        self.reservation_args = args
        return self.reservation

    def get_user_by_normalized_email(self, normalized_email):
        self.requested_email = normalized_email
        return self.user

    def record_login_failure(self, event):
        self.failures.append(event)

    def complete_login(self, **kwargs):
        self.completed.append(kwargs)
        return True

    def authenticate_session(self, **kwargs):
        self.authentication = kwargs
        return self.identity

    def revoke_authenticated_session(self, **kwargs):
        self.logout = kwargs
        return self.revocation


def user(password_hash: str, *, active: bool = True) -> InternalUser:
    return InternalUser(
        id=uuid4(),
        email="Admin@Example.com",
        normalized_email="admin@example.com",
        password_hash=password_hash,
        password_version=1,
        active=active,
        created_at=NOW,
        updated_at=NOW,
        disabled_at=None if active else NOW,
    )


def service(repository, *, semaphore=None):
    return InternalLoginService(
        repository,
        PasswordHasher(),
        RateLimitKeyDeriver(RATE_KEY),
        argon2_slots=semaphore,
    )


def test_generated_tokens_are_canonical_random_and_store_only_digests():
    first = generate_session_secrets()
    second = generate_session_secrets()
    session_id, digest = parse_session_token(first.session_token)
    assert session_id == first.session_id
    assert digest == first.verifier_digest
    assert parse_csrf_token(first.csrf_token) == first.csrf_digest
    assert first.session_token.startswith(f"usiar_s1.{first.session_id}.")
    assert first.session_token != second.session_token
    assert first.csrf_token != second.csrf_token
    assert first.csrf_token not in first.csrf_digest.hex()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "usiar_s1.bad.secret",
        "usiar_s2.00000000-0000-4000-8000-000000000000." + "a" * 43,
    ],
)
def test_malformed_session_tokens_are_rejected(value):
    with pytest.raises(ValueError):
        parse_session_token(value)


def test_rate_limit_secret_is_base64url_and_at_least_32_bytes():
    with pytest.raises(ValueError):
        RateLimitKeyDeriver("short")
    keys = RateLimitKeyDeriver(RATE_KEY)
    assert keys.identifier("admin@example.com") != keys.global_key()
    assert keys.identifier("admin@example.com") == keys.identifier("admin@example.com")


def test_login_creates_30_minute_idle_and_8_hour_absolute_session():
    hasher = PasswordHasher()
    repository = Repository(user(hasher.hash(PASSWORD)))
    created = service(repository).login(
        "Admin@Example.com", PASSWORD, request_id="request-1", now=NOW
    )
    completed = repository.completed[0]
    assert created.idle_expires_at.isoformat() == "2026-10-09T16:30:00+00:00"
    assert created.absolute_expires_at.isoformat() == "2026-10-10T00:00:00+00:00"
    assert completed["event"].event_type == "LOGIN_SUCCESS"
    assert completed["session"].verifier_digest not in created.session_token.encode()
    assert repository.requested_email == "admin@example.com"


@pytest.mark.parametrize("kind", ["missing", "inactive", "wrong"])
def test_invalid_accounts_share_the_same_error_and_are_audited(kind):
    hasher = PasswordHasher()
    account = None
    password = PASSWORD
    if kind != "missing":
        account = user(hasher.hash(PASSWORD), active=kind != "inactive")
    if kind == "wrong":
        password = "outra senha longa segura"
    repository = Repository(account)
    with pytest.raises(InvalidCredentialsError):
        service(repository).login(
            "admin@example.com", password, request_id="request-2", now=NOW
        )
    assert repository.failures[0].event_type == "LOGIN_FAILURE"
    assert repository.completed == []


def test_unknown_user_always_executes_the_dummy_hash_verification():
    class SpyHasher:
        def __init__(self):
            self.verify_calls = []

        def hash(self, _password):
            return "$argon2id$dummy"

        def verify(self, encoded_hash, password):
            self.verify_calls.append((encoded_hash, password))
            return False

        def needs_rehash(self, _encoded_hash):
            return False

    hasher = SpyHasher()
    repository = Repository()
    login = InternalLoginService(repository, hasher, RateLimitKeyDeriver(RATE_KEY))
    with pytest.raises(InvalidCredentialsError):
        login.login("nobody@example.com", PASSWORD, request_id=None, now=NOW)
    assert hasher.verify_calls == [("$argon2id$dummy", PASSWORD)]


def test_rate_limit_and_argon_capacity_fail_closed():
    repository = Repository()
    repository.reservation = LoginAttemptReservation(False, 900)
    with pytest.raises(AuthenticationRateLimitedError) as limited:
        service(repository).login(
            "admin@example.com", PASSWORD, request_id=None, now=NOW
        )
    assert limited.value.retry_after_seconds == 900
    assert repository.failures[0].event_type == "LOGIN_RATE_LIMITED"

    class DeniedSemaphore:
        def acquire(self, *, timeout):
            return False

        def release(self):
            raise AssertionError("an unacquired semaphore must not be released")

    with pytest.raises(AuthenticationCapacityError):
        service(Repository(), semaphore=DeniedSemaphore()).login(
            "admin@example.com", PASSWORD, request_id=None, now=NOW
        )


def test_argon2_work_is_limited_to_two_concurrent_verifications():
    ready = Event()
    release = Event()

    class BlockingHasher:
        def __init__(self):
            self.active = 0
            self.maximum = 0
            self.lock = Lock()

        def hash(self, _password):
            return "$argon2id$dummy"

        def verify(self, _encoded_hash, _password):
            with self.lock:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                if self.active == 2:
                    ready.set()
            release.wait(timeout=2)
            with self.lock:
                self.active -= 1
            return False

        def needs_rehash(self, _encoded_hash):
            return False

    hasher = BlockingHasher()
    login = InternalLoginService(Repository(), hasher, RateLimitKeyDeriver(RATE_KEY))

    def attempt():
        with pytest.raises(InvalidCredentialsError):
            login.login("nobody@example.com", PASSWORD, request_id=None, now=NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        assert ready.wait(timeout=2)
        with pytest.raises(AuthenticationCapacityError):
            login.login("nobody@example.com", PASSWORD, request_id=None, now=NOW)
        release.set()
        for future in futures:
            future.result()
    assert hasher.maximum == 2


def test_session_authentication_and_logout_delegate_only_digests():
    generated = generate_session_secrets()
    repository = Repository()
    repository.identity = AuthenticatedInternalSession(
        UUID("00000000-0000-4000-8000-000000000001"),
        "Admin",
        frozenset({"dashboard:read"}),
    )
    sessions = InternalSessionService(repository)
    assert (
        sessions.authenticate(generated.session_token, now=NOW) == repository.identity
    )
    sessions.logout(
        generated.session_token,
        generated.csrf_token,
        request_id="request-3",
        now=NOW,
    )
    assert repository.authentication["verifier_digest"] == generated.verifier_digest
    assert repository.logout["csrf_digest"] == generated.csrf_digest

    repository.identity = None
    with pytest.raises(InvalidInternalSessionError):
        sessions.authenticate(generated.session_token, now=NOW)
    with pytest.raises(InvalidCsrfTokenError):
        sessions.logout(generated.session_token, "bad", request_id=None, now=NOW)
    repository.revocation = SessionRevocationResult.INVALID_CSRF
    with pytest.raises(InvalidCsrfTokenError):
        sessions.logout(
            generated.session_token,
            generated.csrf_token,
            request_id=None,
            now=NOW,
        )
