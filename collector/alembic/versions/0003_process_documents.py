"""Catálogo e observações de documentos.

Revision ID: 0003_documents
Revises: 0002_screening
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_documents"
down_revision: Union[str, Sequence[str], None] = "0002_screening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "process_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("official_document_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("document_type", sa.Text(), nullable=True),
        sa.Column("document_type_id", sa.Integer(), nullable=True),
        sa.Column("document_type_description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("document_sequence", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('PNCP', 'RHS')", name="ck_process_documents_source"),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_process_documents_process_id_processes",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_process_documents"),
        sa.UniqueConstraint(
            "source",
            "official_document_id",
            name="uq_process_documents_source_official",
        ),
    )
    op.create_index("ix_process_documents_process_id", "process_documents", ["process_id"])

    op.create_table(
        "document_catalog_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("documents_found", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("queried_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_document_catalog_queries_process_id_processes",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["collection_rounds.id"],
            name="fk_document_catalog_queries_round_id_collection_rounds",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_catalog_queries"),
    )
    op.create_index(
        "ix_document_catalog_queries_process_id",
        "document_catalog_queries",
        ["process_id"],
    )
    op.create_index(
        "ix_document_catalog_queries_round_id",
        "document_catalog_queries",
        ["round_id"],
    )

    op.create_table(
        "document_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("document_type", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["query_id"],
            ["document_catalog_queries.id"],
            name="fk_document_observations_query_id_document_catalog_queries",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["process_documents.id"],
            name="fk_document_observations_document_id_process_documents",
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_document_observations_process_id_processes",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_observations"),
        sa.UniqueConstraint(
            "query_id",
            "document_id",
            name="uq_document_observations_query_document",
        ),
    )
    op.create_index(
        "ix_document_observations_query_id", "document_observations", ["query_id"]
    )
    op.create_index(
        "ix_document_observations_document_id",
        "document_observations",
        ["document_id"],
    )
    op.create_index(
        "ix_document_observations_process_id",
        "document_observations",
        ["process_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_observations_process_id", table_name="document_observations")
    op.drop_index("ix_document_observations_document_id", table_name="document_observations")
    op.drop_index("ix_document_observations_query_id", table_name="document_observations")
    op.drop_table("document_observations")
    op.drop_index(
        "ix_document_catalog_queries_round_id", table_name="document_catalog_queries"
    )
    op.drop_index(
        "ix_document_catalog_queries_process_id", table_name="document_catalog_queries"
    )
    op.drop_table("document_catalog_queries")
    op.drop_index("ix_process_documents_process_id", table_name="process_documents")
    op.drop_table("process_documents")
