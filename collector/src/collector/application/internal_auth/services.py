"""Use cases for internal login and opaque sessions."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore
from uuid import uuid4

from .models import (
    AuditEvent,
    AuditOutcome,
    AuthenticatedInternalSession,
    InternalSession,
    SessionRevocationResult,
    normalize_email,
)
from .passwords import PasswordHasher, validate_password
from .ports import InternalAuthRepository
from .rate_limit import LoginRatePolicy, RateLimitKeyDeriver
from .tokens import (
    generate_session_secrets,
    parse_csrf_token,
    parse_session_token,
)

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=8)
TOUCH_INTERVAL_SECONDS = 5 * 60
ARGON2_WAIT_SECONDS = 0.25


class InvalidCredentialsError(Exception):
    pass


class AuthenticationRateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


class AuthenticationCapacityError(Exception):
    pass


class InvalidInternalSessionError(Exception):
    pass


class InvalidCsrfTokenError(Exception):
    pass


@dataclass(frozen=True)
class CreatedSession:
    session_token: str
    csrf_token: str
    idle_expires_at: datetime
    absolute_expires_at: datetime


class InternalLoginService:
    def __init__(
        self,
        repository: InternalAuthRepository,
        password_hasher: PasswordHasher,
        key_deriver: RateLimitKeyDeriver,
        *,
        policy: LoginRatePolicy | None = None,
        argon2_slots: BoundedSemaphore | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._key_deriver = key_deriver
        self._policy = policy or LoginRatePolicy()
        self._argon2_slots = (
            argon2_slots if argon2_slots is not None else BoundedSemaphore(2)
        )
        self._dummy_hash = password_hasher.hash(secrets.token_urlsafe(48))

    def login(
        self,
        email: str,
        password: str,
        *,
        request_id: str | None,
        now: datetime | None = None,
    ) -> CreatedSession:
        normalized_email = normalize_email(email)
        validate_password(password)
        current_time = now or datetime.now(UTC)
        identifier_key = self._key_deriver.identifier(normalized_email)
        reservation = self._repository.reserve_login_attempt(
            identifier_key,
            self._key_deriver.global_key(),
            current_time,
            self._policy,
        )
        if not reservation.allowed:
            self._repository.record_login_failure(
                self._event(
                    "LOGIN_RATE_LIMITED",
                    AuditOutcome.FAILURE,
                    current_time,
                    request_id,
                    None,
                )
            )
            raise AuthenticationRateLimitedError(reservation.retry_after_seconds or 1)
        if not self._argon2_slots.acquire(timeout=ARGON2_WAIT_SECONDS):
            raise AuthenticationCapacityError
        try:
            user = self._repository.get_user_by_normalized_email(normalized_email)
            encoded_hash = user.password_hash if user is not None else self._dummy_hash
            password_matches = self._password_hasher.verify(encoded_hash, password)
        finally:
            self._argon2_slots.release()

        if user is None or not user.active or not password_matches:
            self._repository.record_login_failure(
                self._event(
                    "LOGIN_FAILURE",
                    AuditOutcome.FAILURE,
                    current_time,
                    request_id,
                    user.id if user is not None else None,
                )
            )
            raise InvalidCredentialsError

        replacement_hash = None
        if self._password_hasher.needs_rehash(user.password_hash):
            if not self._argon2_slots.acquire(timeout=ARGON2_WAIT_SECONDS):
                raise AuthenticationCapacityError
            try:
                replacement_hash = self._password_hasher.hash(password)
            finally:
                self._argon2_slots.release()

        secrets_bundle = generate_session_secrets()
        absolute_expires_at = current_time + ABSOLUTE_TIMEOUT
        idle_expires_at = min(current_time + IDLE_TIMEOUT, absolute_expires_at)
        password_version = user.password_version + (replacement_hash is not None)
        session = InternalSession(
            id=secrets_bundle.session_id,
            verifier_digest=secrets_bundle.verifier_digest,
            csrf_digest=secrets_bundle.csrf_digest,
            user_id=user.id,
            password_version=password_version,
            created_at=current_time,
            last_seen_at=current_time,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        completed = self._repository.complete_login(
            user_id=user.id,
            expected_password_version=user.password_version,
            expected_password_hash=user.password_hash,
            replacement_password_hash=replacement_hash,
            identifier_digest=identifier_key,
            session=session,
            event=self._event(
                "LOGIN_SUCCESS",
                AuditOutcome.SUCCESS,
                current_time,
                request_id,
                user.id,
            ),
        )
        if not completed:
            raise InvalidCredentialsError
        return CreatedSession(
            session_token=secrets_bundle.session_token,
            csrf_token=secrets_bundle.csrf_token,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )

    @staticmethod
    def _event(
        event_type: str,
        outcome: AuditOutcome,
        now: datetime,
        request_id: str | None,
        subject_user_id,
    ) -> AuditEvent:
        return AuditEvent(
            id=uuid4(),
            event_type=event_type,
            outcome=outcome,
            occurred_at=now,
            created_at=now,
            subject_user_id=subject_user_id,
            request_id=request_id,
        )


class InternalSessionService:
    def __init__(self, repository: InternalAuthRepository) -> None:
        self._repository = repository

    def authenticate(
        self, token: str, *, now: datetime | None = None
    ) -> AuthenticatedInternalSession:
        try:
            session_id, verifier_digest = parse_session_token(token)
        except ValueError as exc:
            raise InvalidInternalSessionError from exc
        identity = self._repository.authenticate_session(
            session_id=session_id,
            verifier_digest=verifier_digest,
            now=now or datetime.now(UTC),
            touch_after_seconds=TOUCH_INTERVAL_SECONDS,
            idle_timeout_seconds=int(IDLE_TIMEOUT.total_seconds()),
        )
        if identity is None:
            raise InvalidInternalSessionError
        return identity

    def logout(
        self,
        token: str,
        csrf_token: str,
        *,
        request_id: str | None,
        now: datetime | None = None,
    ) -> None:
        try:
            session_id, verifier_digest = parse_session_token(token)
        except ValueError as exc:
            raise InvalidInternalSessionError from exc
        try:
            csrf_digest = parse_csrf_token(csrf_token)
        except ValueError as exc:
            raise InvalidCsrfTokenError from exc
        current_time = now or datetime.now(UTC)
        event = AuditEvent(
            id=uuid4(),
            event_type="SESSION_REVOKED",
            outcome=AuditOutcome.SUCCESS,
            occurred_at=current_time,
            created_at=current_time,
            request_id=request_id,
        )
        result = self._repository.revoke_authenticated_session(
            session_id=session_id,
            verifier_digest=verifier_digest,
            csrf_digest=csrf_digest,
            now=current_time,
            event=event,
        )
        if result is SessionRevocationResult.INVALID_CSRF:
            raise InvalidCsrfTokenError
        if result is SessionRevocationResult.INVALID:
            raise InvalidInternalSessionError
