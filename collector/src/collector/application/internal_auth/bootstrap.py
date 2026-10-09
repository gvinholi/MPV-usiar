"""Atomic first-user bootstrap application service."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .models import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    AuditOutcome,
    InternalUser,
    normalize_email,
)
from .passwords import PasswordHasher
from .ports import InternalAuthRepository


class BootstrapAlreadyCompletedError(RuntimeError):
    pass


class BootstrapAdmin:
    def __init__(
        self,
        repository: InternalAuthRepository,
        hasher: PasswordHasher | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ):
        self._repository = repository
        self._hasher = hasher or PasswordHasher()
        self._clock = clock
        self._id_factory = id_factory

    def execute(self, email: str, password: str) -> UUID:
        normalized = normalize_email(email)
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware timestamp")
        now = now.astimezone(UTC)
        user_id = self._id_factory()
        user = InternalUser(
            id=user_id,
            email=normalized,
            normalized_email=normalized,
            password_hash=self._hasher.hash(password),
            password_version=1,
            active=True,
            created_at=now,
            updated_at=now,
        )
        event = AuditEvent(
            id=self._id_factory(),
            event_type="BOOTSTRAP_ADMIN",
            outcome=AuditOutcome.SUCCESS,
            subject_user_id=user_id,
            occurred_at=now,
            created_at=now,
        )
        self._repository.bootstrap_admin(user, ADMIN_PERMISSIONS, event)
        return user_id
