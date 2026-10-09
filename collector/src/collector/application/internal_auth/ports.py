"""Persistence boundary for internal identities and authentication state."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .models import (
    AuditEvent,
    InternalPermission,
    InternalSession,
    InternalUser,
    LoginAttempt,
)


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
