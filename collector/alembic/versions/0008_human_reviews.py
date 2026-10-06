"""Append-only human review audit trail.

Revision ID: 0008_human_reviews
Revises: 0007_operational
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_human_reviews"
down_revision = "0007_operational"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "human_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("operational_resolution_id", sa.Uuid(), sa.ForeignKey("operational_resolutions.id"), nullable=False),
        sa.Column("reviewer_id", sa.Text(), nullable=False),
        sa.Column("reviewer_display_name", sa.Text()),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("idempotency_key", sa.Text(), nullable=False, unique=True),
        sa.Column("allow_stale", sa.Boolean(), nullable=False),
        sa.Column("was_stale_at_decision", sa.Boolean(), nullable=False),
        sa.Column("latest_resolution_id_at_decision", sa.Uuid(), sa.ForeignKey("operational_resolutions.id"), nullable=False),
        sa.Column("resolution_fingerprint", sa.Text(), nullable=False),
        sa.Column("operational_state_snapshot", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('SELECTED','DISCARDED','PENDING')", name="human_decision"),
        sa.CheckConstraint("""
            (decision = 'SELECTED' AND reason_code IN
                ('RELEVANT_SCOPE_CONFIRMED','COMMERCIAL_INTEREST','TECHNICAL_FIT','REVIEWED_AND_APPROVED')) OR
            (decision = 'DISCARDED' AND reason_code IN
                ('OUT_OF_SCOPE','ISOLATED_INSTALLATION','EQUIPMENT_PURCHASE_ONLY','PARTS_SUPPLY_ONLY',
                 'DEADLINE_NOT_VIABLE','TECHNICAL_REQUIREMENT_NOT_VIABLE','COMMERCIAL_DECISION','DUPLICATE_OPPORTUNITY','OTHER')) OR
            (decision = 'PENDING' AND reason_code IN
                ('NEEDS_TECHNICAL_REVIEW','NEEDS_COMMERCIAL_REVIEW','NEEDS_DOCUMENT_REVIEW','INSUFFICIENT_INFORMATION','OTHER'))
        """, name="human_reason_compatibility"),
        sa.CheckConstraint("reason_code <> 'OTHER' OR (comment IS NOT NULL AND comment ~ '[^[:space:]]')", name="human_other_comment"),
        sa.CheckConstraint("comment IS NULL OR length(comment) <= 4000", name="human_comment_length"),
        sa.CheckConstraint("reviewer_id ~ '[^[:space:]]' AND length(reviewer_id) <= 200", name="human_reviewer"),
        sa.CheckConstraint("reviewer_display_name IS NULL OR (reviewer_display_name ~ '[^[:space:]]' AND length(reviewer_display_name) <= 200)", name="human_display_name"),
        sa.CheckConstraint("idempotency_key ~ '[^[:space:]]' AND length(idempotency_key) <= 200", name="human_key"),
        sa.CheckConstraint("operational_state_snapshot IN ('CANDIDATE','PENDING','DISCARDED')", name="human_operational_state"),
        sa.CheckConstraint("was_stale_at_decision = (operational_resolution_id <> latest_resolution_id_at_decision) AND (NOT was_stale_at_decision OR allow_stale)", name="human_stale_audit"),
    )
    op.create_index("ix_human_reviews_latest", "human_reviews", ["operational_resolution_id", "decided_at", "created_at", "sequence"])
    # Immutable audit rows, even when accessed outside the application repository.
    op.execute("""
        CREATE FUNCTION reject_human_review_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'human_reviews is append-only';
        END; $$
    """)
    op.execute("CREATE TRIGGER human_reviews_append_only BEFORE UPDATE OR DELETE ON human_reviews FOR EACH ROW EXECUTE FUNCTION reject_human_review_mutation()")
    op.execute("""
        CREATE FUNCTION validate_human_review_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM operational_resolutions r
                JOIN operational_resolutions l ON l.id = NEW.latest_resolution_id_at_decision
                WHERE r.id = NEW.operational_resolution_id
                  AND r.process_id = l.process_id AND r.profile_id = l.profile_id
                  AND r.state = NEW.operational_state_snapshot
                  AND r.resolution_fingerprint = NEW.resolution_fingerprint
            ) THEN
                RAISE EXCEPTION 'human review snapshot or resolution scope mismatch';
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute("CREATE TRIGGER human_reviews_snapshot BEFORE INSERT ON human_reviews FOR EACH ROW EXECUTE FUNCTION validate_human_review_snapshot()")


def downgrade():
    op.drop_table("human_reviews")
    op.execute("DROP FUNCTION validate_human_review_snapshot()")
    op.execute("DROP FUNCTION reject_human_review_mutation()")
