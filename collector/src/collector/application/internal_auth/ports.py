"""Persistence boundary for internal identities and authentication state."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .models import (
    AuditEvent,
    AuthenticatedInternalSession,
    InternalPermission,
    InternalSession,
    InternalUser,
    LoginAttempt,
    LoginAttemptReservation,
    SessionRevocationResult,
)


class LoginRateLimitPolicy(Protocol):
    identifier_limit: int
    identifier_window_seconds: int
    identifier_block_seconds: int
    global_limit: int
    global_window_seconds: int
    global_block_seconds: int


class InternalAuthRepository(Protocol):
    def bootstrap_admin(
        self,
        user: InternalUser,
        permissions: frozenset[InternalPermission],
        event: AuditEvent,
    ) -> None: ...
    def count_users(self) -> int: ...
    def get_user_by_normalized_email(
        self, normalized_email: str
    ) -> InternalUser | None: ...
    def permissions_for_user(self, user_id: UUID) -> frozenset[InternalPermission]: ...
    def create_session(self, session: InternalSession) -> None: ...
    def get_session(self, session_id: UUID) -> InternalSession | None: ...
    def revoke_session(
        self, session_id: UUID, revoked_at: datetime, reason: str
    ) -> bool: ...
    def save_login_attempt(self, attempt: LoginAttempt) -> None: ...
    def get_login_attempt(self, key_digest: bytes) -> LoginAttempt | None: ...
    def append_audit_event(self, event: AuditEvent) -> None: ...
    def reserve_login_attempt(
        self,
        identifier_digest: bytes,
        global_digest: bytes,
        now: datetime,
        policy: LoginRateLimitPolicy,
    ) -> LoginAttemptReservation: ...
    def record_login_failure(self, event: AuditEvent) -> None: ...
    def complete_login(
        self,
        *,
        user_id: UUID,
        expected_password_version: int,
        expected_password_hash: str,
        replacement_password_hash: str | None,
        identifier_digest: bytes,
        session: InternalSession,
        event: AuditEvent,
    ) -> bool: ...
    def authenticate_session(
        self,
        *,
        session_id: UUID,
        verifier_digest: bytes,
        now: datetime,
        touch_after_seconds: int,
        idle_timeout_seconds: int,
    ) -> AuthenticatedInternalSession | None: ...
    def revoke_authenticated_session(
        self,
        *,
        session_id: UUID,
        verifier_digest: bytes,
        csrf_digest: bytes,
        now: datetime,
        event: AuditEvent,
    ) -> SessionRevocationResult: ...
