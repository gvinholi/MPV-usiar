"""Schema inicial: rodadas, modalidades, processos, identidades e observações.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collection_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("pages_expected", sa.Integer(), nullable=False),
        sa.Column("pages_processed", sa.Integer(), nullable=False),
        sa.Column("pages_with_error", sa.Integer(), nullable=False),
        sa.Column("records_collected", sa.Integer(), nullable=False),
        sa.Column("unique_processes", sa.Integer(), nullable=False),
        sa.Column("candidates", sa.Integer(), nullable=False),
        sa.Column("selected", sa.Integer(), nullable=False),
        sa.Column("pending", sa.Integer(), nullable=False),
        sa.Column("discarded", sa.Integer(), nullable=False),
        sa.Column("documents_found", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')",
            name="ck_collection_rounds_status",
        ),
        sa.CheckConstraint("source IN ('PNCP', 'RHS')", name="ck_collection_rounds_source"),
        sa.PrimaryKeyConstraint("id", name="pk_collection_rounds"),
    )

    op.create_table(
        "processes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_processes"),
    )

    op.create_table(
        "collection_modality_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("modality_code", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("pages_processed", sa.Integer(), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("processes_mapped", sa.Integer(), nullable=False),
        sa.Column("failed_page", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "mapping_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["collection_rounds.id"],
            name="fk_collection_modality_outcomes_round_id_collection_rounds",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_modality_outcomes"),
        sa.UniqueConstraint(
            "round_id",
            "modality_code",
            name="uq_modality_outcomes_round_code",
        ),
    )
    op.create_index(
        "ix_collection_modality_outcomes_round_id",
        "collection_modality_outcomes",
        ["round_id"],
    )

    op.create_table(
        "source_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("official_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('PNCP', 'RHS')", name="ck_source_identities_source"),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_source_identities_process_id_processes",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_identities"),
        sa.UniqueConstraint(
            "source",
            "official_id",
            name="uq_source_identities_source_official",
        ),
    )
    op.create_index(
        "ix_source_identities_process_id",
        "source_identities",
        ["process_id"],
    )

    op.create_table(
        "process_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_name", sa.Text(), nullable=True),
        sa.Column("organization_cnpj", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("modality", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("locality", sa.Text(), nullable=True),
        sa.Column("estimated_value", sa.Numeric(), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('PNCP', 'RHS')", name="ck_process_observations_source"),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_process_observations_process_id_processes",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["collection_rounds.id"],
            name="fk_process_observations_round_id_collection_rounds",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_process_observations"),
        sa.UniqueConstraint(
            "round_id",
            "process_id",
            name="uq_process_observations_round_process",
        ),
    )
    op.create_index(
        "ix_process_observations_process_id",
        "process_observations",
        ["process_id"],
    )
    op.create_index(
        "ix_process_observations_round_id",
        "process_observations",
        ["round_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_observations_round_id", table_name="process_observations")
    op.drop_index("ix_process_observations_process_id", table_name="process_observations")
    op.drop_table("process_observations")
    op.drop_index("ix_source_identities_process_id", table_name="source_identities")
    op.drop_table("source_identities")
    op.drop_index(
        "ix_collection_modality_outcomes_round_id",
        table_name="collection_modality_outcomes",
    )
    op.drop_table("collection_modality_outcomes")
    op.drop_table("processes")
    op.drop_table("collection_rounds")
