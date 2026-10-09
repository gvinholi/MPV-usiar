"""PostgreSQL persistence for internal users and opaque-session records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from collector.application.internal_auth import (
    AuditEvent,
    AuditOutcome,
    BootstrapAlreadyCompletedError,
    InternalPermission,
    InternalSession,
    InternalUser,
    LoginAttempt,
)
from collector.infra.database.models import (
    AuthAuditEventRow,
    AuthLoginAttemptRow,
    AuthPermissionRow,
    AuthSessionRow,
    AuthUserPermissionRow,
    AuthUserRow,
)

BOOTSTRAP_LOCK = "usiar-internal-auth-bootstrap-v1"


def _user(row: AuthUserRow) -> InternalUser:
    return InternalUser(
        id=row.id,
        email=row.email,
        normalized_email=row.normalized_email,
        password_hash=row.password_hash,
        password_version=row.password_version,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        display_name=row.display_name,
        last_login_at=row.last_login_at,
        disabled_at=row.disabled_at,
    )


def _session(row: AuthSessionRow) -> InternalSession:
    return InternalSession(
        id=row.id,
        verifier_digest=bytes(row.verifier_digest),
        csrf_digest=bytes(row.csrf_digest),
        user_id=row.user_id,
        password_version=row.password_version,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        idle_expires_at=row.idle_expires_at,
        absolute_expires_at=row.absolute_expires_at,
        revoked_at=row.revoked_at,
        revoke_reason=row.revoke_reason,
    )


def _attempt(row: AuthLoginAttemptRow) -> LoginAttempt:
    return LoginAttempt(
        key_digest=bytes(row.key_digest),
        failure_count=row.failure_count,
        window_started_at=row.window_started_at,
        last_failure_at=row.last_failure_at,
        blocked_until=row.blocked_until,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit_row(event: AuditEvent) -> AuthAuditEventRow:
    return AuthAuditEventRow(
        id=event.id,
        event_type=event.event_type,
        outcome=event.outcome.value,
        subject_user_id=event.subject_user_id,
        actor_user_id=event.actor_user_id,
        request_id=event.request_id,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
    )


class SqlAlchemyInternalAuthRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def bootstrap_admin(
        self,
        user: InternalUser,
        permissions: frozenset[InternalPermission],
        event: AuditEvent,
    ) -> None:
        if (
            event.subject_user_id != user.id
            or event.actor_user_id is not None
            or event.outcome is not AuditOutcome.SUCCESS
        ):
            raise ValueError("invalid bootstrap audit event")
        if permissions != frozenset(InternalPermission):
            raise ValueError("bootstrap requires the complete Admin/Dev permission set")
        with self._session_factory.begin() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": BOOTSTRAP_LOCK},
            )
            if session.scalar(select(func.count()).select_from(AuthUserRow)):
                raise BootstrapAlreadyCompletedError("an internal user already exists")
            available = frozenset(
                InternalPermission(code)
                for code in session.scalars(
                    select(AuthPermissionRow.code).where(
                        AuthPermissionRow.code.in_([p.value for p in permissions])
                    )
                )
            )
            if available != permissions:
                raise RuntimeError("internal permission catalog is incomplete")
            session.add(
                AuthUserRow(
                    id=user.id,
                    email=user.email,
                    normalized_email=user.normalized_email,
                    display_name=user.display_name,
                    password_hash=user.password_hash,
                    password_version=user.password_version,
                    active=user.active,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    last_login_at=user.last_login_at,
                    disabled_at=user.disabled_at,
                )
            )
            session.flush()
            session.add_all(
                [
                    AuthUserPermissionRow(
                        user_id=user.id,
                        permission_code=permission.value,
                        granted_at=user.created_at,
                        granted_by=None,
                    )
                    for permission in sorted(permissions, key=lambda item: item.value)
                ]
            )
            session.add(_audit_row(event))

    def count_users(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(AuthUserRow)) or 0

    def get_user_by_normalized_email(
        self, normalized_email: str
    ) -> InternalUser | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(AuthUserRow).where(
                    AuthUserRow.normalized_email == normalized_email
                )
            )
            return _user(row) if row else None

    def permissions_for_user(self, user_id: UUID) -> frozenset[InternalPermission]:
        with self._session_factory() as session:
            codes = session.scalars(
                select(AuthUserPermissionRow.permission_code).where(
                    AuthUserPermissionRow.user_id == user_id
                )
            )
            return frozenset(InternalPermission(code) for code in codes)

    def create_session(self, value: InternalSession) -> None:
        with self._session_factory.begin() as session:
            session.add(
                AuthSessionRow(
                    id=value.id,
                    verifier_digest=value.verifier_digest,
                    csrf_digest=value.csrf_digest,
                    user_id=value.user_id,
                    password_version=value.password_version,
                    created_at=value.created_at,
                    last_seen_at=value.last_seen_at,
                    idle_expires_at=value.idle_expires_at,
                    absolute_expires_at=value.absolute_expires_at,
                    revoked_at=value.revoked_at,
                    revoke_reason=value.revoke_reason,
                )
            )

    def get_session(self, session_id: UUID) -> InternalSession | None:
        with self._session_factory() as session:
            row = session.get(AuthSessionRow, session_id)
            return _session(row) if row else None

    def revoke_session(
        self, session_id: UUID, revoked_at: datetime, reason: str
    ) -> bool:
        if revoked_at.utcoffset() is None or not reason.strip() or len(reason) > 100:
            raise ValueError("invalid revocation")
        with self._session_factory.begin() as session:
            result = session.execute(
                update(AuthSessionRow)
                .where(
                    AuthSessionRow.id == session_id,
                    AuthSessionRow.revoked_at.is_(None),
                )
                .values(revoked_at=revoked_at, revoke_reason=reason)
            )
            return result.rowcount == 1

    def save_login_attempt(self, attempt: LoginAttempt) -> None:
        values = {
            "key_digest": attempt.key_digest,
            "failure_count": attempt.failure_count,
            "window_started_at": attempt.window_started_at,
            "last_failure_at": attempt.last_failure_at,
            "blocked_until": attempt.blocked_until,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
        with self._session_factory.begin() as session:
            session.execute(
                insert(AuthLoginAttemptRow)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[AuthLoginAttemptRow.key_digest],
                    set_={
                        key: value
                        for key, value in values.items()
                        if key not in {"key_digest", "created_at"}
                    },
                )
            )

    def get_login_attempt(self, key_digest: bytes) -> LoginAttempt | None:
        with self._session_factory() as session:
            row = session.get(AuthLoginAttemptRow, key_digest)
            return _attempt(row) if row else None

    def append_audit_event(self, event: AuditEvent) -> None:
        with self._session_factory.begin() as session:
            session.add(_audit_row(event))
