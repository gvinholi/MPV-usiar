"""Resolução operacional entre triagens inicial e documental.

Revision ID: 0007_operational
Revises: 0006_document_screening
Create Date: 2026-10-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_operational"
down_revision: Union[str, Sequence[str], None] = "0006_document_screening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operational_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("initial_evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolver_engine_version", sa.Text(), nullable=False),
        sa.Column("resolution_fingerprint", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("coverage_complete", sa.Boolean(), nullable=False),
        sa.Column("state_diverged", sa.Boolean(), nullable=True),
        sa.Column("reason_diverged", sa.Boolean(), nullable=True),
        sa.Column("initial_state", sa.Text(), nullable=False),
        sa.Column("document_state", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="ck_operational_resolutions_state",
        ),
        sa.CheckConstraint(
            "initial_state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="ck_operational_resolutions_initial_state",
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_operational_res_process_id",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["screening_profiles.id"],
            name="fk_operational_res_profile_id",
        ),
        sa.ForeignKeyConstraint(
            ["initial_evaluation_id"],
            ["screening_evaluations.id"],
            name="fk_operational_res_initial_id",
        ),
        sa.ForeignKeyConstraint(
            ["document_evaluation_id"],
            ["document_screening_evaluations.id"],
            name="fk_operational_res_document_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operational_resolutions"),
        sa.UniqueConstraint(
            "process_id",
            "profile_id",
            "resolver_engine_version",
            "resolution_fingerprint",
            name="uq_operational_res_process_profile_engine_fp",
        ),
    )
    op.create_index(
        "ix_operational_res_process_id",
        "operational_resolutions",
        ["process_id"],
    )
    op.create_index(
        "ix_operational_res_profile_id",
        "operational_resolutions",
        ["profile_id"],
    )
    op.create_index(
        "ix_operational_res_initial_id",
        "operational_resolutions",
        ["initial_evaluation_id"],
    )
    op.create_index(
        "ix_operational_res_document_id",
        "operational_resolutions",
        ["document_evaluation_id"],
    )
    op.create_index(
        "ix_operational_res_latest",
        "operational_resolutions",
        ["process_id", "resolved_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_operational_res_latest", table_name="operational_resolutions")
    op.drop_index("ix_operational_res_document_id", table_name="operational_resolutions")
    op.drop_index("ix_operational_res_initial_id", table_name="operational_resolutions")
    op.drop_index("ix_operational_res_profile_id", table_name="operational_resolutions")
    op.drop_index("ix_operational_res_process_id", table_name="operational_resolutions")
    op.drop_table("operational_resolutions")
