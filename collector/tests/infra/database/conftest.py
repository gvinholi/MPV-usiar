"""PostgreSQL real via DATABASE_URL. Sem SQLite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from collector.application import PersistCollection
from collector.infra.database import SqlAlchemyCollectionRepository

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL).strip()


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = _database_url()
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL indisponível: {exc}")
    return url


@pytest.fixture(scope="session")
def migrated_engine(postgres_url: str) -> Engine:
    config = Config(str(COLLECTOR_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(COLLECTOR_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(COLLECTOR_ROOT / "src"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")
    return create_engine(postgres_url, pool_pre_ping=True)


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE collection_rounds, processes "
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
