"""Persisted collection lease with fencing token.

Revision ID: 0013_collection_leases
Revises: 0012_supabase_hardening

The TypeScript runner reaches PostgreSQL through Cloudflare Hyperdrive, which
pools connections in transaction mode: consecutive statements may run on
different server sessions, so a session-level advisory lock is neither held
nor released reliably. Mutual exclusion moves to one row per lease:

- acquire: a single conditional UPDATE (free or expired) that increments
  ``fencing_token``; concurrent acquirers serialize on the row lock and only one
  matches the predicate;
- renew/release: conditional on ``owner_id`` + ``fencing_token`` + not expired;
- fencing: every write transaction of a run starts with ``SELECT ... FOR SHARE``
  on its own (owner, token) and aborts if the lease was lost. The share lock
  makes a takeover wait for in-flight transactions, so an old run can never
  commit after a newer run acquired the lease.

All timestamps come from the database clock (``clock_timestamp()``), never from
Worker or host clocks. The Python legacy collector uses the same row.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_collection_leases"
down_revision = "0012_supabase_hardening"
branch_labels = None
depends_on = None

PNCP_LEASE = "PNCP_COLLECTION"
GUARD_FUNCTION = "public.guard_collection_lease_update()"
FUNCTION_SEARCH_PATH = "pg_catalog, public, pg_temp"


def upgrade() -> None:
    op.create_table(
        "collection_leases",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("owner_kind", sa.Text(), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("name", name="pk_collection_leases"),
        sa.CheckConstraint("name ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_collection_leases_name"),
        sa.CheckConstraint("fencing_token >= 0", name="ck_collection_leases_token"),
        sa.CheckConstraint(
            "owner_kind IS NULL OR owner_kind ~ '^[a-z][a-z0-9:_-]{0,63}$'",
            name="ck_collection_leases_owner_kind",
        ),
        sa.CheckConstraint(
            "(owner_id IS NULL AND owner_kind IS NULL AND expires_at IS NULL) OR "
            "(owner_id IS NOT NULL AND owner_kind IS NOT NULL AND acquired_at IS NOT NULL "
            "AND heartbeat_at IS NOT NULL AND expires_at > heartbeat_at)",
            name="ck_collection_leases_owner",
        ),
    )
    # Rows are fixed by migration: the runtime role only UPDATEs them.
    op.execute(f"INSERT INTO collection_leases (name) VALUES ('{PNCP_LEASE}')")
    op.execute('ALTER TABLE "collection_leases" ENABLE ROW LEVEL SECURITY')

    # Defense in depth for the runtime role's UPDATE grant: the token is
    # monotonic and the lease identity is immutable, so fencing cannot be
    # rewound by any client.
    op.execute(
        f"""
        CREATE FUNCTION {GUARD_FUNCTION} RETURNS trigger
        LANGUAGE plpgsql SET search_path = {FUNCTION_SEARCH_PATH} AS $$
        BEGIN
            IF NEW.name IS DISTINCT FROM OLD.name THEN
                RAISE EXCEPTION 'collection_leases.name is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.fencing_token < OLD.fencing_token THEN
                RAISE EXCEPTION 'collection_leases.fencing_token must not decrease'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.owner_id IS DISTINCT FROM OLD.owner_id AND NEW.owner_id IS NOT NULL
               AND NEW.fencing_token <= OLD.fencing_token THEN
                RAISE EXCEPTION 'collection_leases: new owner requires a new fencing token'
                    USING ERRCODE = 'check_violation';
            END IF;
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {GUARD_FUNCTION} FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_collection_leases_guard BEFORE UPDATE ON collection_leases "
        f"FOR EACH ROW EXECUTE FUNCTION {GUARD_FUNCTION}"
    )


def downgrade() -> None:
    op.drop_table("collection_leases")
    op.execute(f"DROP FUNCTION {GUARD_FUNCTION}")
