"""Explicit Supabase administrator allowlist.

Revision ID: 0011_supabase_admins
Revises: 0010_pncp_official_fields
"""

import sqlalchemy as sa

from alembic import op

revision = "0011_supabase_admins"
down_revision = "0010_pncp_official_fields"
branch_labels = None
depends_on = None

APPLICATION_TABLES = (
    "collection_rounds",
    "processes",
    "collection_modality_outcomes",
    "source_identities",
    "process_observations",
    "screening_profiles",
    "screening_evaluations",
    "screening_evidence",
    "process_documents",
    "document_catalog_queries",
    "document_observations",
    "artifacts",
    "document_artifacts",
    "artifact_archive_entries",
    "artifact_text_sources",
    "text_extractions",
    "text_extraction_pages",
    "document_screening_evaluations",
    "document_screening_evidence",
    "operational_resolutions",
    "human_reviews",
    "auth_users",
    "auth_permissions",
    "auth_user_permissions",
    "auth_sessions",
    "auth_login_attempts",
    "auth_audit_events",
)


def upgrade() -> None:
    op.create_table(
        "app_admins",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "email = lower(email) AND email ~ '^[^[:space:]@]+@[^[:space:]@]+$'",
            name="ck_app_admins_email",
        ),
    )
    # Supabase PostgREST must not expose any application table. No Data API
    # policies are created. The Worker uses a direct/session PostgreSQL
    # connection as the table owner and therefore does not depend on PostgREST.
    for table in (*APPLICATION_TABLES, "app_admins"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("app_admins")
    for table in APPLICATION_TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
