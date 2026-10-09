"""Internal Admin/Dev authentication persistence foundation.

Revision ID: 0009_internal_auth
Revises: 0008_human_reviews
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009_internal_auth"
down_revision = "0008_human_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("normalized_email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("password_version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(email) BETWEEN 3 AND 320", name="ck_auth_users_email_length"
        ),
        sa.CheckConstraint(
            "length(normalized_email) BETWEEN 3 AND 320",
            name="ck_auth_users_normalized_email_length",
        ),
        sa.CheckConstraint(
            "normalized_email = lower(normalized_email)",
            name="ck_auth_users_normalized_email_lower",
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%'", name="ck_auth_users_argon2id"
        ),
        sa.CheckConstraint(
            "password_version >= 1", name="ck_auth_users_password_version"
        ),
        sa.CheckConstraint(
            "display_name IS NULL OR (display_name ~ '[^[:space:]]' AND length(display_name) <= 200)",
            name="ck_auth_users_display_name",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name="ck_auth_users_timestamp_order"
        ),
        sa.CheckConstraint(
            "(active AND disabled_at IS NULL) OR (NOT active AND disabled_at IS NOT NULL)",
            name="ck_auth_users_active_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_users"),
        sa.UniqueConstraint("normalized_email", name="uq_auth_users_normalized_email"),
    )

    op.create_table(
        "auth_permissions",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_-]{0,31}:[a-z][a-z0-9_-]{0,31}$'",
            name="ck_auth_permissions_code",
        ),
        sa.CheckConstraint(
            "description ~ '[^[:space:]]' AND length(description) <= 200",
            name="ck_auth_permissions_description",
        ),
        sa.PrimaryKeyConstraint("code", name="pk_auth_permissions"),
    )

    op.create_table(
        "auth_user_permissions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_code", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name="fk_auth_user_permissions_user_id_auth_users",
        ),
        sa.ForeignKeyConstraint(
            ["permission_code"],
            ["auth_permissions.code"],
            name="fk_auth_user_permissions_permission_code_auth_permissions",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["auth_users.id"],
            name="fk_auth_user_permissions_granted_by_auth_users",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "permission_code", name="pk_auth_user_permissions"
        ),
    )
    op.create_index(
        "ix_auth_user_permissions_permission_code",
        "auth_user_permissions",
        ["permission_code"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verifier_digest", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_digest", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "octet_length(verifier_digest) = 32",
            name="ck_auth_sessions_verifier_digest",
        ),
        sa.CheckConstraint(
            "octet_length(csrf_digest) = 32", name="ck_auth_sessions_csrf_digest"
        ),
        sa.CheckConstraint(
            "password_version >= 1", name="ck_auth_sessions_password_version"
        ),
        sa.CheckConstraint(
            "last_seen_at >= created_at", name="ck_auth_sessions_last_seen"
        ),
        sa.CheckConstraint(
            "last_seen_at < idle_expires_at",
            name="ck_auth_sessions_last_seen_expiration",
        ),
        sa.CheckConstraint(
            "idle_expires_at > created_at AND idle_expires_at <= absolute_expires_at",
            name="ck_auth_sessions_idle_expiration",
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name="ck_auth_sessions_absolute_expiration",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoke_reason IS NULL) OR (revoked_at IS NOT NULL AND revoke_reason ~ '[^[:space:]]' AND length(revoke_reason) <= 100)",
            name="ck_auth_sessions_revocation",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["auth_users.id"], name="fk_auth_sessions_user_id_auth_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("verifier_digest", name="uq_auth_sessions_verifier_digest"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_expiration",
        "auth_sessions",
        ["absolute_expires_at", "idle_expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "auth_login_attempts",
        sa.Column("key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(key_digest) = 32", name="ck_auth_login_attempts_key_digest"
        ),
        sa.CheckConstraint(
            "failure_count >= 0", name="ck_auth_login_attempts_failure_count"
        ),
        sa.CheckConstraint(
            "last_failure_at >= window_started_at",
            name="ck_auth_login_attempts_failure_order",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name="ck_auth_login_attempts_update_order"
        ),
        sa.CheckConstraint(
            "blocked_until IS NULL OR blocked_until > last_failure_at",
            name="ck_auth_login_attempts_block_order",
        ),
        sa.PrimaryKeyConstraint("key_digest", name="pk_auth_login_attempts"),
    )
    op.create_index(
        "ix_auth_login_attempts_blocked_until",
        "auth_login_attempts",
        ["blocked_until"],
        postgresql_where=sa.text("blocked_until IS NOT NULL"),
    )

    op.create_table(
        "auth_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_auth_audit_events_type"
        ),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS','FAILURE')", name="ck_auth_audit_events_outcome"
        ),
        sa.CheckConstraint(
            "request_id IS NULL OR request_id ~ '^[A-Za-z0-9._:-]{1,128}$'",
            name="ck_auth_audit_events_request_id",
        ),
        sa.CheckConstraint(
            "created_at >= occurred_at", name="ck_auth_audit_events_timestamp_order"
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"],
            ["auth_users.id"],
            name="fk_auth_audit_events_subject_user_id_auth_users",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["auth_users.id"],
            name="fk_auth_audit_events_actor_user_id_auth_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_audit_events"),
    )
    op.create_index(
        "ix_auth_audit_events_subject_time",
        "auth_audit_events",
        ["subject_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_auth_audit_events_type_time",
        "auth_audit_events",
        ["event_type", "occurred_at"],
    )

    permissions = sa.table(
        "auth_permissions",
        sa.column("code", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    created_at = datetime.now(UTC)
    op.bulk_insert(
        permissions,
        [
            {
                "code": "dashboard:read",
                "description": "Consultar o dashboard operacional.",
                "created_at": created_at,
            },
            {
                "code": "reviews:write",
                "description": "Registrar revisoes humanas.",
                "created_at": created_at,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_audit_events_type_time", table_name="auth_audit_events")
    op.drop_index("ix_auth_audit_events_subject_time", table_name="auth_audit_events")
    op.drop_table("auth_audit_events")
    op.drop_index(
        "ix_auth_login_attempts_blocked_until", table_name="auth_login_attempts"
    )
    op.drop_table("auth_login_attempts")
    op.drop_index("ix_auth_sessions_expiration", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        "ix_auth_user_permissions_permission_code", table_name="auth_user_permissions"
    )
    op.drop_table("auth_user_permissions")
    op.drop_table("auth_permissions")
    op.drop_table("auth_users")
