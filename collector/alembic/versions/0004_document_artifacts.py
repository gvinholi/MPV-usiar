"""Artefatos técnicos e aquisições documentais.

Revision ID: 0004_artifacts
Revises: 0003_documents
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_artifacts"
down_revision: Union[str, Sequence[str], None] = "0003_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("hash_algorithm", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("detected_type", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("hash_algorithm = 'sha256'", name="ck_artifacts_hash_algorithm"),
        sa.CheckConstraint(
            "detected_type IN ('PDF', 'ZIP', 'UNKNOWN')",
            name="ck_artifacts_detected_type",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
        sa.UniqueConstraint("sha256", name="uq_artifacts_sha256"),
    )

    op.create_table(
        "document_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=True),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("http_content_type", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("bytes_received", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["process_documents.id"],
            name="fk_document_artifacts_document_id_process_documents",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_document_artifacts_artifact_id_artifacts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_artifacts"),
    )
    op.create_index(
        "ix_document_artifacts_document_id", "document_artifacts", ["document_id"]
    )
    op.create_index(
        "ix_document_artifacts_artifact_id", "document_artifacts", ["artifact_id"]
    )

    op.create_table(
        "artifact_archive_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_path", sa.Text(), nullable=False),
        sa.Column("compressed_size", sa.Integer(), nullable=True),
        sa.Column("uncompressed_size", sa.Integer(), nullable=True),
        sa.Column("is_directory", sa.Boolean(), nullable=False),
        sa.Column("extension", sa.Text(), nullable=True),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False),
        sa.Column("is_symlink", sa.Boolean(), nullable=False),
        sa.Column("has_unsafe_path", sa.Boolean(), nullable=False),
        sa.Column("unsafe_path_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_artifact_archive_entries_artifact_id_artifacts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_archive_entries"),
    )
    op.create_index(
        "ix_artifact_archive_entries_artifact_id",
        "artifact_archive_entries",
        ["artifact_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_artifact_archive_entries_artifact_id",
        table_name="artifact_archive_entries",
    )
    op.drop_table("artifact_archive_entries")
    op.drop_index("ix_document_artifacts_artifact_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_document_id", table_name="document_artifacts")
    op.drop_table("document_artifacts")
    op.drop_table("artifacts")
