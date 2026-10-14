"""Hardening Supabase: Data API, RLS, privilégios padrão e role de runtime.

Simula o que importa do Supabase num banco descartável do cluster local:
- dono do banco/migrations sem SUPERUSER, com CREATEROLE (como `postgres`);
- roles da Data API (anon, authenticated, service_role com BYPASSRLS);
- default privileges que concedem ALL em objetos novos de public a essas roles.
Cria roles no cluster local de teste; nunca roda contra host remoto (ver conftest).
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from psycopg import errors, sql
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, ProgrammingError

from alembic import command
from collector.infra.database import SqlAlchemyOperationalRunLock

from .conftest import (
    RUNTIME_ROLE,
    alembic_config,
    apply_runtime_role_script,
    runtime_role_url,
)

pytestmark = pytest.mark.postgres

DB_NAME = "usiar_mig_supabase"
MIGRATION_ROLE = "usiar_test_supabase_postgres"
DATA_API_ROLES = ("anon", "authenticated", "service_role")
HEAD = "0013_collection_leases"
ALL_TABLE_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER"

S = frozenset({"SELECT"})
SI = frozenset({"SELECT", "INSERT"})
SIU = frozenset({"SELECT", "INSERT", "UPDATE"})
EXPECTED_RUNTIME_GRANTS = {
    "collection_rounds": SIU,
    "collection_modality_outcomes": SI,
    # UPDATE só por coluna (ver COLLECTION_LEASES_UPDATABLE); sem INSERT/DELETE.
    "collection_leases": S,
    "processes": SIU,
    "source_identities": SI,
    "process_observations": SI,
    "screening_profiles": SI,
    "screening_evaluations": SI,
    "screening_evidence": SI,
    "operational_resolutions": SI,
    "process_documents": SIU,
    "document_catalog_queries": SI,
    "document_observations": SI,
    "artifacts": SI,
    "document_artifacts": SI,
    "artifact_archive_entries": SI,
    "artifact_text_sources": SI,
    "text_extractions": SI,
    "text_extraction_pages": SI,
    "document_screening_evaluations": SI,
    "document_screening_evidence": SI,
    "human_reviews": SI,
    "auth_users": S,
    "auth_permissions": S,
    "auth_user_permissions": S,
    "auth_sessions": SIU,
    "auth_login_attempts": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
    "auth_audit_events": SI,
    "app_admins": S,
}
AUTH_USERS_UPDATABLE = {"password_hash", "password_version", "last_login_at", "updated_at"}
COLLECTION_LEASES_UPDATABLE = {
    "owner_id", "owner_kind", "fencing_token", "acquired_at", "heartbeat_at", "expires_at", "released_at",
}


@dataclass(frozen=True)
class SupabaseLikeDatabase:
    superuser: Engine
    migration_url: str
    migration: Engine


def _execute_raw(engine: Engine, statement: sql.Composable | str) -> None:
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(statement)
        raw.commit()
    finally:
        raw.close()


def _create_role_if_missing(engine: Engine, name: str, attributes: str) -> None:
    exists = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    with exists as connection:
        if connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": name}):
            return
    _execute_raw(engine, sql.SQL("CREATE ROLE {} " + attributes).format(sql.Identifier(name)))


@pytest.fixture(scope="module")
def supabase_db(postgres_url: str) -> Iterator[SupabaseLikeDatabase]:
    cluster = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        if not connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")):
            cluster.dispose()
            pytest.skip("simulação Supabase requer superusuário no cluster local de teste")
        connection.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
    for role in ("anon", "authenticated"):
        _create_role_if_missing(cluster, role, "NOLOGIN NOINHERIT")
    _create_role_if_missing(cluster, "service_role", "NOLOGIN NOINHERIT BYPASSRLS")
    _create_role_if_missing(cluster, MIGRATION_ROLE, "LOGIN NOSUPERUSER CREATEROLE")
    migration_password = secrets.token_urlsafe(24)
    _execute_raw(
        cluster,
        sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(MIGRATION_ROLE), sql.Literal(migration_password)
        ),
    )
    with cluster.connect() as connection:
        # usiar_runtime é global no cluster e pode ter sido criada por outro
        # superusuário (modo USIAR_TEST_RUNTIME_ROLE). No Supabase quem a cria é
        # o próprio postgres, que por isso tem ADMIN sobre ela no PostgreSQL 16+.
        if connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_ROLE}):
            connection.execute(text(f"GRANT {RUNTIME_ROLE} TO {MIGRATION_ROLE} WITH ADMIN OPTION"))
        connection.execute(text(f"CREATE DATABASE {DB_NAME} OWNER {MIGRATION_ROLE}"))

    base = make_url(postgres_url).set(database=DB_NAME)
    superuser = create_engine(base.render_as_string(hide_password=False), pool_pre_ping=True)
    with superuser.begin() as connection:
        connection.execute(text(f"ALTER SCHEMA public OWNER TO {MIGRATION_ROLE}"))
        roles = ", ".join(DATA_API_ROLES)
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {roles}"))
        connection.execute(text(f"GRANT {roles} TO {MIGRATION_ROLE}"))
        for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
            connection.execute(
                text(
                    f"ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATION_ROLE} IN SCHEMA public "
                    f"GRANT ALL ON {kind} TO {roles}"
                )
            )
    migration_url = base.set(
        username=MIGRATION_ROLE, password=migration_password
    ).render_as_string(hide_password=False)
    command.upgrade(alembic_config(migration_url), "head")
    migration = create_engine(migration_url, pool_pre_ping=True)
    try:
        yield SupabaseLikeDatabase(superuser, migration_url, migration)
    finally:
        migration.dispose()
        superuser.dispose()
        with cluster.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
        cluster.dispose()


@pytest.fixture(scope="module")
def runtime_engine(supabase_db: SupabaseLikeDatabase) -> Iterator[Engine]:
    apply_runtime_role_script(supabase_db.migration)
    engine = create_engine(
        runtime_role_url(supabase_db.migration, supabase_db.migration_url), pool_pre_ping=True
    )
    try:
        yield engine
    finally:
        engine.dispose()


def _public_tables(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
            ).scalars()
        )


def _exposed_objects(engine: Engine, role: str) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    """
                    SELECT 'table ' || c.relname FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND CASE WHEN c.relkind IN ('r','p','v','m')
                      THEN has_table_privilege(:role, c.oid, :table_privileges) ELSE false END
                    UNION ALL
                    SELECT 'sequence ' || c.relname FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND CASE WHEN c.relkind = 'S'
                      THEN has_sequence_privilege(:role, c.oid, 'USAGE, SELECT, UPDATE') ELSE false END
                    UNION ALL
                    SELECT 'function ' || p.proname FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND has_function_privilege(:role, p.oid, 'EXECUTE')
                    ORDER BY 1
                    """
                ),
                {"role": role, "table_privileges": ALL_TABLE_PRIVILEGES},
            ).scalars()
        )


# ---------------------------------------------------------------- Data API / RLS


def test_supabase_like_database_reaches_head(supabase_db):
    with supabase_db.migration.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert connection.scalar(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ) is False


@pytest.mark.parametrize("role", DATA_API_ROLES)
def test_data_api_roles_have_no_effective_privileges(supabase_db, role):
    assert _exposed_objects(supabase_db.superuser, role) == []


def test_alembic_version_is_protected(supabase_db):
    with supabase_db.superuser.connect() as connection:
        assert connection.scalar(
            text("SELECT relrowsecurity FROM pg_class WHERE oid = 'public.alembic_version'::regclass")
        ) is True
        for role in DATA_API_ROLES:
            assert connection.scalar(
                text("SELECT has_table_privilege(:r, 'public.alembic_version', :p)"),
                {"r": role, "p": ALL_TABLE_PRIVILEGES},
            ) is False
    for role in ("anon", "authenticated"):
        with supabase_db.superuser.connect() as connection:
            connection.execute(text(f"SET ROLE {role}"))
            with pytest.raises(ProgrammingError) as caught:
                connection.execute(text("SELECT version_num FROM public.alembic_version"))
            assert isinstance(caught.value.orig, errors.InsufficientPrivilege)
            connection.rollback()


def test_every_public_table_has_rls_enabled(supabase_db):
    with supabase_db.superuser.connect() as connection:
        without_rls = list(
            connection.execute(
                text(
                    "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind IN ('r','p') AND NOT c.relrowsecurity"
                )
            ).scalars()
        )
    assert without_rls == []
    assert "alembic_version" in _public_tables(supabase_db.superuser)


def test_default_privileges_do_not_expose_new_objects(supabase_db):
    with supabase_db.migration.connect() as connection:
        connection.execute(text("CREATE TABLE public.zz_probe (id bigint GENERATED ALWAYS AS IDENTITY)"))
        connection.execute(text("CREATE SEQUENCE public.zz_probe_seq"))
        connection.execute(
            text("CREATE FUNCTION public.zz_probe_fn() RETURNS int LANGUAGE sql AS 'SELECT 1'")
        )
        try:
            for role in (*DATA_API_ROLES, "public"):
                exposed = connection.execute(
                    text(
                        "SELECT has_table_privilege(:r, 'public.zz_probe', :p) "
                        "OR has_sequence_privilege(:r, 'public.zz_probe_seq', 'USAGE, SELECT, UPDATE') "
                        "OR has_function_privilege(:r, 'public.zz_probe_fn()', 'EXECUTE')"
                    ),
                    {"r": role, "p": ALL_TABLE_PRIVILEGES},
                ).scalar()
                assert exposed is False, role
        finally:
            connection.rollback()


def test_human_review_trigger_functions_pin_search_path(supabase_db):
    with supabase_db.superuser.connect() as connection:
        rows = dict(
            connection.execute(
                text(
                    "SELECT proname, proconfig FROM pg_proc WHERE pronamespace = 'public'::regnamespace "
                    "AND proname IN ('reject_human_review_mutation', 'validate_human_review_snapshot')"
                )
            ).all()
        )
        public_execute = connection.scalar(
            text(
                "SELECT bool_or(has_function_privilege('public', p.oid, 'EXECUTE')) FROM pg_proc p "
                "WHERE p.pronamespace = 'public'::regnamespace"
            )
        )
    assert rows == {
        "reject_human_review_mutation": ["search_path=pg_catalog, public, pg_temp"],
        "validate_human_review_snapshot": ["search_path=pg_catalog, public, pg_temp"],
    }
    assert public_execute is False


def test_downgrade_does_not_reexpose_and_upgrade_is_repeatable(supabase_db):
    config = alembic_config(supabase_db.migration_url)
    command.downgrade(config, "0011_supabase_admins")
    try:
        with supabase_db.superuser.connect() as connection:
            assert connection.scalar(
                text("SELECT relrowsecurity FROM pg_class WHERE oid = 'public.alembic_version'::regclass")
            ) is False
            assert connection.scalar(
                text(
                    "SELECT proconfig FROM pg_proc WHERE proname = 'validate_human_review_snapshot'"
                )
            ) is None
        # Só o EXECUTE de PUBLIC nas funções de trigger volta (estado da 0011);
        # tabelas e sequências continuam fora da Data API.
        for role in DATA_API_ROLES:
            exposed = _exposed_objects(supabase_db.superuser, role)
            assert all(item.startswith("function ") for item in exposed), exposed
    finally:
        command.upgrade(config, "head")
    for role in DATA_API_ROLES:
        assert _exposed_objects(supabase_db.superuser, role) == []


# ----------------------------------------------------------------- runtime role


def test_runtime_role_attributes_are_minimal(runtime_engine, supabase_db):
    with supabase_db.superuser.connect() as connection:
        row = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolreplication, rolcreaterole, rolcreatedb, "
                "rolinherit, rolcanlogin FROM pg_roles WHERE rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        ).one()
        memberships = connection.scalar(
            text(
                "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
                "WHERE r.rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        )
        owned = connection.scalar(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
                "WHERE r.rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        )
    assert tuple(row) == (False, False, False, False, False, False, True)
    assert memberships == 0
    assert owned == 0


def test_runtime_role_grants_match_reviewed_map(runtime_engine, supabase_db):
    with supabase_db.superuser.connect() as connection:
        grants: dict[str, set[str]] = {}
        for table, privilege in connection.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = :r AND table_schema = 'public'"
            ),
            {"r": RUNTIME_ROLE},
        ):
            grants.setdefault(table, set()).add(privilege)
        updatable: dict[str, set[str]] = {}
        for table, column in connection.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.column_privileges "
                "WHERE grantee = :r AND table_schema = 'public' AND privilege_type = 'UPDATE' "
                "AND table_name IN ('auth_users', 'collection_leases')"
            ),
            {"r": RUNTIME_ROLE},
        ):
            updatable.setdefault(table, set()).add(column)
        sequences = connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.usage_privileges "
                "WHERE grantee = :r AND object_type = 'SEQUENCE'"
            ),
            {"r": RUNTIME_ROLE},
        )
    assert {table: frozenset(privs) for table, privs in grants.items()} == EXPECTED_RUNTIME_GRANTS
    assert updatable == {
        "auth_users": AUTH_USERS_UPDATABLE,
        "collection_leases": COLLECTION_LEASES_UPDATABLE,
    }
    assert sequences == 0
    assert set(_public_tables(supabase_db.superuser)) - set(EXPECTED_RUNTIME_GRANTS) == {
        "alembic_version"
    }


def test_runtime_role_policies_match_grants(runtime_engine, supabase_db):
    with supabase_db.superuser.connect() as connection:
        policies: dict[str, set[str]] = {}
        for table, command_name in connection.execute(
            text(
                "SELECT tablename, cmd FROM pg_policies WHERE schemaname = 'public' "
                "AND :r = ANY(roles)"
            ),
            {"r": RUNTIME_ROLE},
        ):
            policies.setdefault(table, set()).add(command_name)
    expected = {table: set(privs) for table, privs in EXPECTED_RUNTIME_GRANTS.items()}
    expected["auth_users"] = {"SELECT", "UPDATE"}
    expected["collection_leases"] = {"SELECT", "UPDATE"}
    assert policies == expected


def test_runtime_role_script_is_idempotent(runtime_engine, supabase_db):
    apply_runtime_role_script(supabase_db.migration)
    test_runtime_role_grants_match_reviewed_map(runtime_engine, supabase_db)
    test_runtime_role_policies_match_grants(runtime_engine, supabase_db)


def test_runtime_role_script_rejects_unmapped_tables(runtime_engine, supabase_db):
    with supabase_db.migration.begin() as connection:
        connection.execute(text("CREATE TABLE public.zz_unmapped (id int)"))
    try:
        with pytest.raises(errors.RaiseException, match="zz_unmapped"):
            apply_runtime_role_script(supabase_db.migration)
    finally:
        with supabase_db.migration.begin() as connection:
            connection.execute(text("DROP TABLE public.zz_unmapped"))


def test_runtime_role_reads_and_writes_through_rls(runtime_engine):
    process_id = uuid4()
    with runtime_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO processes (id, created_at, updated_at) VALUES (:id, now(), now())"),
            {"id": process_id},
        )
        connection.execute(
            text("UPDATE processes SET updated_at = now() WHERE id = :id"), {"id": process_id}
        )
    with runtime_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT count(*) FROM processes WHERE id = :id"), {"id": process_id}
        ) == 1
        assert connection.scalar(text("SELECT count(*) FROM app_admins")) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE public.zz_runtime (id int)",
        "ALTER TABLE processes ADD COLUMN zz int",
        "DROP TABLE app_admins",
        "TRUNCATE processes",
        "DELETE FROM human_reviews",
        "DELETE FROM processes",
        "UPDATE auth_users SET active = false",
        "UPDATE auth_users SET email = 'x@example.com'",
        "INSERT INTO app_admins (user_id, email) VALUES (gen_random_uuid(), 'x@example.com')",
        "INSERT INTO auth_users (id) VALUES (gen_random_uuid())",
        "SELECT version_num FROM alembic_version",
        "INSERT INTO collection_leases (name) VALUES ('ZZ_LEASE')",
        "DELETE FROM collection_leases",
        "UPDATE collection_leases SET name = 'ZZ_LEASE'",
        "ALTER TABLE collection_leases DISABLE TRIGGER trg_collection_leases_guard",
        "ALTER TABLE processes DISABLE ROW LEVEL SECURITY",
        "CREATE ROLE zz_runtime_escalation",
        "SET ROLE anon",
        "CREATE SCHEMA zz_runtime",
    ],
)
def test_runtime_role_cannot_escalate_or_change_schema(runtime_engine, statement):
    with runtime_engine.connect() as connection:
        with pytest.raises(DBAPIError) as caught:
            connection.execute(text(statement))
        assert isinstance(caught.value.orig, errors.InsufficientPrivilege)
        connection.rollback()


def test_runtime_role_operates_collection_lease(runtime_engine):
    first = SqlAlchemyOperationalRunLock(runtime_engine)
    second = SqlAlchemyOperationalRunLock(runtime_engine)
    with first.acquire() as acquired:
        assert acquired is True
        first.assert_held()
        with second.acquire() as contended:
            assert contended is False
    with second.acquire() as after_release:
        assert after_release is True
    # Locks de transação seguem disponíveis (revisão humana e auth interna).
    with runtime_engine.begin() as connection:
        assert connection.scalar(text("SELECT pg_try_advisory_xact_lock(42)")) is True
