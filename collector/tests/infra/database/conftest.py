"""PostgreSQL real via DATABASE_URL. Sem SQLite."""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from collector.application import PersistCollection
from collector.infra.database import SqlAlchemyCollectionRepository

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"
RUNTIME_ROLE_SCRIPT = COLLECTOR_ROOT / "sql" / "runtime_role.sql"
RUNTIME_ROLE = "usiar_runtime"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL).strip()


def _runtime_role_mode() -> bool:
    """USIAR_TEST_RUNTIME_ROLE=1 roda a suíte com a role de runtime restrita."""
    return os.environ.get("USIAR_TEST_RUNTIME_ROLE") == "1"


def alembic_config(url: str) -> Config:
    config = Config(str(COLLECTOR_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(COLLECTOR_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(COLLECTOR_ROOT / "src"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def apply_runtime_role_script(admin: Engine) -> None:
    """Aplica collector/sql/runtime_role.sql numa transação, como o psql faria."""
    raw = admin.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(RUNTIME_ROLE_SCRIPT.read_text(encoding="utf-8"))
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()


def runtime_role_url(admin: Engine, admin_url: str) -> str:
    """Senha aleatória só para o cluster local de teste; nunca é registrada."""
    password = secrets.token_urlsafe(24)
    raw = admin.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(RUNTIME_ROLE), sql.Literal(password)
                )
            )
        raw.commit()
    finally:
        raw.close()
    return make_url(admin_url).set(username=RUNTIME_ROLE, password=password).render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = _database_url()
    # Os testes truncam tabelas e criam bancos/roles: nunca contra Supabase ou
    # outro host remoto sem opt-in explícito.
    host = make_url(url).host or "localhost"
    if host not in LOCAL_HOSTS and os.environ.get("USIAR_TEST_ALLOW_REMOTE_DB") != "1":
        pytest.skip("PostgreSQL de teste recusado: DATABASE_URL não aponta para host local")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Só o tipo do erro: mensagens do driver podem conter host e usuário.
        pytest.skip(f"PostgreSQL indisponível: {type(exc).__name__}")
    finally:
        engine.dispose()
    return url


@pytest.fixture(scope="session")
def admin_engine(postgres_url: str) -> Engine:
    """Credencial administrativa: migrations, truncates e preparação de dados."""
    command.upgrade(alembic_config(postgres_url), "head")
    return create_engine(postgres_url, pool_pre_ping=True)


@pytest.fixture(scope="session")
def migrated_engine(admin_engine: Engine, postgres_url: str) -> Engine:
    """Engine usada pelo código da aplicação nos testes."""
    if not _runtime_role_mode():
        return admin_engine
    apply_runtime_role_script(admin_engine)
    return create_engine(runtime_role_url(admin_engine, postgres_url), pool_pre_ping=True)


@pytest.fixture
def db_session(migrated_engine: Engine, admin_engine: Engine) -> Iterator[Session]:
    with admin_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE auth_login_attempts, auth_audit_events, auth_sessions, "
                "auth_user_permissions, auth_users, collection_rounds, processes, "
                "screening_profiles, artifacts "
                "RESTART IDENTITY CASCADE"
            )
        )
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def persist_service(migrated_engine: Engine, db_session: Session) -> PersistCollection:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistCollection(SqlAlchemyCollectionRepository(factory))
