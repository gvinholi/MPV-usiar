"""Provider-independent identity records and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from email_validator import EmailNotValidError, validate_email


class InternalPermission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    REVIEWS_WRITE = "reviews:write"


ADMIN_PERMISSIONS = frozenset(InternalPermission)


class AuditOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def normalize_email(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("invalid email")
    try:
        normalized = validate_email(
            value, check_deliverability=False
        ).normalized.casefold()
    except EmailNotValidError as exc:
        raise ValueError("invalid email") from exc
    if not 3 <= len(normalized) <= 320:
        raise ValueError("invalid email")
    return normalized


@dataclass(frozen=True)
class InternalUser:
    id: UUID
    email: str
    normalized_email: str
    password_hash: str
    password_version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    display_name: str | None = None
    last_login_at: datetime | None = None
    disabled_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.normalized_email != normalize_email(self.email):
            raise ValueError("email is not normalized")
        if not self.password_hash.startswith("$argon2id$"):
            raise ValueError("Argon2id password hash required")
        if type(self.password_version) is not int or self.password_version < 1:
            raise ValueError("invalid password version")
        if self.display_name is not None and (
            not self.display_name.strip() or len(self.display_name) > 200
        ):
            raise ValueError("invalid display name")
        _aware(self.created_at, "created_at")
        _aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        if self.last_login_at is not None:
            _aware(self.last_login_at, "last_login_at")
        if self.disabled_at is not None:
            _aware(self.disabled_at, "disabled_at")
        if self.active == (self.disabled_at is not None):
            raise ValueError("active and disabled_at disagree")


@dataclass(frozen=True)
class InternalSession:
    id: UUID
    verifier_digest: bytes
    csrf_digest: bytes
    user_id: UUID
    password_version: int
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = None

    def __post_init__(self) -> None:
        if len(self.verifier_digest) != 32 or len(self.csrf_digest) != 32:
            raise ValueError("session digests must be SHA-256")
        if self.password_version < 1:
            raise ValueError("invalid password version")
        for name in (
            "created_at",
            "last_seen_at",
            "idle_expires_at",
            "absolute_expires_at",
        ):
            _aware(getattr(self, name), name)
        if (
            not self.created_at
            <= self.last_seen_at
            < self.idle_expires_at
            <= self.absolute_expires_at
        ):
            raise ValueError("invalid session timestamps")
        if self.revoked_at is not None:
            _aware(self.revoked_at, "revoked_at")
        if (self.revoked_at is None) != (self.revoke_reason is None):
            raise ValueError("invalid revocation")
        if self.revoke_reason is not None and (
            not self.revoke_reason.strip() or len(self.revoke_reason) > 100
        ):
            raise ValueError("invalid revoke reason")


@dataclass(frozen=True)
class LoginAttempt:
    key_digest: bytes
    failure_count: int
    window_started_at: datetime
    last_failure_at: datetime
    created_at: datetime
    updated_at: datetime
    blocked_until: datetime | None = None

    def __post_init__(self) -> None:
        if (
            len(self.key_digest) != 32
            or type(self.failure_count) is not int
            or self.failure_count < 0
        ):
            raise ValueError("invalid login attempt")
        for name in (
            "window_started_at",
            "last_failure_at",
            "created_at",
            "updated_at",
        ):
            _aware(getattr(self, name), name)
        if (
            self.last_failure_at < self.window_started_at
            or self.updated_at < self.created_at
        ):
            raise ValueError("invalid login attempt timestamps")
        if self.blocked_until is not None:
            _aware(self.blocked_until, "blocked_until")
            if self.blocked_until <= self.last_failure_at:
                raise ValueError("invalid blocked_until")


@dataclass(frozen=True)
class AuditEvent:
    id: UUID
    event_type: str
    outcome: AuditOutcome
    occurred_at: datetime
    created_at: datetime
    subject_user_id: UUID | None = None
    actor_user_id: UUID | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.event_type) is None:
            raise ValueError("invalid audit event type")
        _aware(self.occurred_at, "occurred_at")
        _aware(self.created_at, "created_at")
        if self.created_at < self.occurred_at:
            raise ValueError("created_at precedes occurred_at")
        if self.request_id is not None and (
            not self.request_id
            or len(self.request_id) > 128
            or any(not (c.isalnum() or c in "._:-") for c in self.request_id)
        ):
            raise ValueError("invalid request id")


@dataclass(frozen=True)
class LoginAttemptReservation:
    allowed: bool
    retry_after_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.allowed != (self.retry_after_seconds is None):
            raise ValueError("invalid rate-limit reservation")
        if self.retry_after_seconds is not None and self.retry_after_seconds < 1:
            raise ValueError("invalid retry delay")


@dataclass(frozen=True)
class AuthenticatedInternalSession:
    user_id: UUID
    display_name: str | None
    permissions: frozenset[str]


class SessionRevocationResult(StrEnum):
    REVOKED = "revoked"
    ALREADY_REVOKED = "already_revoked"
    INVALID_CSRF = "invalid_csrf"
    INVALID = "invalid"
