"""Extração textual por página e fontes de artefato.

Revision ID: 0005_text
Revises: 0004_artifacts
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_text"
down_revision: Union[str, Sequence[str], None] = "0004_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifact_text_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archive_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("detected_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "detected_type IN ('PDF', 'ZIP', 'UNKNOWN')",
            name="ck_artifact_text_sources_detected_type",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_artifact_text_sources_artifact_id_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["archive_entry_id"],
            ["artifact_archive_entries.id"],
            name="fk_text_sources_archive_entry_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_text_sources"),
        sa.UniqueConstraint(
            "artifact_id",
            "source_path",
            "sha256",
            name="uq_artifact_text_sources_artifact_path_sha",
        ),
    )
    op.create_index(
        "ix_artifact_text_sources_artifact_id",
        "artifact_text_sources",
        ["artifact_id"],
    )

    op.create_table(
        "text_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extractor_name", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("pages_with_text", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("likely_scanned", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DIGITAL_TEXT', 'EMPTY_TEXT', 'LIKELY_SCANNED', 'FAILED', 'UNSUPPORTED')",
            name="ck_text_extractions_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["artifact_text_sources.id"],
            name="fk_text_extractions_source_id_artifact_text_sources",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_text_extractions"),
        sa.UniqueConstraint(
            "source_id",
            "extractor_name",
            "extractor_version",
            name="uq_text_extractions_source_extractor_version",
        ),
    )
    op.create_index("ix_text_extractions_source_id", "text_extractions", ["source_id"])

    op.create_table(
        "text_extraction_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["text_extractions.id"],
            name="fk_text_extraction_pages_extraction_id_text_extractions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_text_extraction_pages"),
        sa.UniqueConstraint(
            "extraction_id",
            "page_number",
            name="uq_text_extraction_pages_extraction_page",
        ),
    )
    op.create_index(
        "ix_text_extraction_pages_extraction_id",
        "text_extraction_pages",
        ["extraction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_text_extraction_pages_extraction_id", table_name="text_extraction_pages"
    )
    op.drop_table("text_extraction_pages")
    op.drop_index("ix_text_extractions_source_id", table_name="text_extractions")
    op.drop_table("text_extractions")
    op.drop_index(
        "ix_artifact_text_sources_artifact_id", table_name="artifact_text_sources"
    )
    op.drop_table("artifact_text_sources")
