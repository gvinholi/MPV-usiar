"""Triagem documental e evidências por página.

Revision ID: 0006_document_screening
Revises: 0005_text
Create Date: 2026-10-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_document_screening"
down_revision: Union[str, Sequence[str], None] = "0005_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_screening_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column("document_set_fingerprint", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("documents_considered", sa.Integer(), nullable=False),
        sa.Column("sources_considered", sa.Integer(), nullable=False),
        sa.Column("pages_considered", sa.Integer(), nullable=False),
        sa.Column("pages_with_text", sa.Integer(), nullable=False),
        sa.Column("likely_scanned_sources", sa.Integer(), nullable=False),
        sa.Column("failed_sources", sa.Integer(), nullable=False),
        sa.Column("unsupported_sources", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="ck_doc_screening_evaluations_state",
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["processes.id"],
            name="fk_doc_screening_eval_process_id",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["screening_profiles.id"],
            name="fk_doc_screening_eval_profile_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_screening_evaluations"),
        sa.UniqueConstraint(
            "process_id",
            "profile_id",
            "engine_version",
            "document_set_fingerprint",
            name="uq_doc_screening_eval_process_profile_engine_fp",
        ),
    )
    op.create_index(
        "ix_doc_screening_eval_process_id",
        "document_screening_evaluations",
        ["process_id"],
    )
    op.create_index(
        "ix_doc_screening_eval_profile_id",
        "document_screening_evaluations",
        ["profile_id"],
    )

    op.create_table(
        "document_screening_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("configured_term", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=False),
        sa.Column("context_snippet", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.Text(), nullable=False),
        sa.Column("negated", sa.Boolean(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["document_screening_evaluations.id"],
            name="fk_doc_screening_ev_evaluation_id",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_page_id"],
            ["text_extraction_pages.id"],
            name="fk_doc_screening_ev_page_id",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["process_documents.id"],
            name="fk_doc_screening_ev_document_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["artifact_text_sources.id"],
            name="fk_doc_screening_ev_source_id",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_doc_screening_ev_artifact_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_screening_evidence"),
    )
    op.create_index(
        "ix_doc_screening_ev_evaluation_id",
        "document_screening_evidence",
        ["evaluation_id"],
    )
    op.create_index(
        "ix_doc_screening_ev_page_id",
        "document_screening_evidence",
        ["extraction_page_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_doc_screening_ev_page_id", table_name="document_screening_evidence")
    op.drop_index(
        "ix_doc_screening_ev_evaluation_id", table_name="document_screening_evidence"
    )
    op.drop_table("document_screening_evidence")
    op.drop_index(
        "ix_doc_screening_eval_profile_id", table_name="document_screening_evaluations"
    )
    op.drop_index(
        "ix_doc_screening_eval_process_id", table_name="document_screening_evaluations"
    )
    op.drop_table("document_screening_evaluations")
