"""Triagem: perfis, avaliações e evidências.

Revision ID: 0002_screening
Revises: 0001_initial
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_screening"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "screening_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_screening_profiles"),
        sa.UniqueConstraint("code", "version", name="uq_screening_profiles_code_version"),
    )

    op.create_table(
        "screening_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="ck_screening_evaluations_state",
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_screening_evaluations_process_id_processes",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["process_observations.id"],
            name="fk_screening_evaluations_observation_id_process_observations",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["screening_profiles.id"],
            name="fk_screening_evaluations_profile_id_screening_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_screening_evaluations"),
        sa.UniqueConstraint(
            "observation_id",
            "profile_id",
            "engine_version",
            name="uq_screening_evaluations_observation_profile_engine",
        ),
    )
    op.create_index(
        "ix_screening_evaluations_process_id",
        "screening_evaluations",
        ["process_id"],
    )
    op.create_index(
        "ix_screening_evaluations_observation_id",
        "screening_evaluations",
        ["observation_id"],
    )
    op.create_index(
        "ix_screening_evaluations_profile_id",
        "screening_evaluations",
        ["profile_id"],
    )

    op.create_table(
        "screening_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("configured_term", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["screening_evaluations.id"],
            name="fk_screening_evidence_evaluation_id_screening_evaluations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_screening_evidence"),
    )
    op.create_index(
        "ix_screening_evidence_evaluation_id",
        "screening_evidence",
        ["evaluation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_screening_evidence_evaluation_id", table_name="screening_evidence")
    op.drop_table("screening_evidence")
    op.drop_index("ix_screening_evaluations_profile_id", table_name="screening_evaluations")
    op.drop_index(
        "ix_screening_evaluations_observation_id", table_name="screening_evaluations"
    )
    op.drop_index("ix_screening_evaluations_process_id", table_name="screening_evaluations")
    op.drop_table("screening_evaluations")
    op.drop_table("screening_profiles")
