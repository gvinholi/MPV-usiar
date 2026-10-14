"""Supabase Data API hardening for public schema objects.

Revision ID: 0012_supabase_hardening
Revises: 0011_supabase_admins

0011 enabled RLS on application tables, but Supabase also grants table,
sequence and function privileges to its Data API roles through default
privileges, and Alembic's own ``alembic_version`` table was left out. This
revision closes those gaps without touching the Supabase-managed ``auth`` and
``storage`` schemas. On plain PostgreSQL (local/CI) the Data API roles do not
exist and the role-specific statements are skipped.
"""

from alembic import op

revision = "0012_supabase_hardening"
down_revision = "0011_supabase_admins"
branch_labels = None
depends_on = None

# Roles that PostgREST (Supabase Data API) switches into. service_role bypasses
# RLS, so it is revoked too: the application never uses the service key.
DATA_API_ROLES = ("anon", "authenticated", "service_role")

TRIGGER_FUNCTIONS = (
    "public.reject_human_review_mutation()",
    "public.validate_human_review_snapshot()",
)

# Explicit path keeps the original unqualified lookups (operational_resolutions)
# resolving to public, and pg_temp last prevents temporary-object shadowing.
FUNCTION_SEARCH_PATH = "pg_catalog, public, pg_temp"


def _for_existing_data_api_roles(statements: tuple[str, ...]) -> str:
    body = "\n".join(f"            EXECUTE format('{s}', r);" for s in statements)
    roles = ", ".join(f"'{role}'" for role in DATA_API_ROLES)
    return f"""
    DO $$
    DECLARE r text;
    BEGIN
        FOREACH r IN ARRAY ARRAY[{roles}] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
{body}
            END IF;
        END LOOP;
    END $$
    """


def upgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute(
        _for_existing_data_api_roles(
            (
                "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I",
                "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I",
                "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I",
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I",
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I",
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I",
            )
        )
    )
    # Trigger functions only need EXECUTE at CREATE TRIGGER time; firing does not
    # check it. PUBLIC (and therefore anon) must not call them through RPC.
    for function in TRIGGER_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {function} SET search_path = {FUNCTION_SEARCH_PATH}")
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    # PostgreSQL grants EXECUTE to PUBLIC on new functions through a global
    # default that per-schema defaults cannot remove. Applies to functions later
    # created by the migration role only.
    op.execute("ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")


def downgrade() -> None:
    # Structural reversal only: privileges revoked from the Data API roles are
    # intentionally not granted back, so a downgrade never re-exposes data.
    op.execute("ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC")
    for function in TRIGGER_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO PUBLIC")
        op.execute(f"ALTER FUNCTION {function} RESET search_path")
    op.execute("ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY")
