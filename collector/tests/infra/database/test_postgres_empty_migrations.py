"""Migration limpa: banco vazio sobe 0001 → head."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.postgres

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
EMPTY_DB = "usiar_mig_empty"


def test_alembic_upgrade_from_empty_database(postgres_url: str) -> None:
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {EMPTY_DB}"))
        connection.execute(text(f"CREATE DATABASE {EMPTY_DB}"))
    empty_url = postgres_url.rsplit("/", 1)[0] + f"/{EMPTY_DB}"
    try:
        config = Config(str(COLLECTOR_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(COLLECTOR_ROOT / "alembic"))
        config.set_main_option("prepend_sys_path", str(COLLECTOR_ROOT / "src"))
        config.set_main_option("sqlalchemy.url", empty_url)
        command.upgrade(config, "head")
        engine = create_engine(empty_url)
        with engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).scalars()
            )
            versions = list(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
            )
        engine.dispose()
        assert "collection_rounds" in tables
        assert "screening_evaluations" in tables
        assert "process_documents" in tables
        assert "artifacts" in tables
        assert "text_extraction_pages" in tables
        assert "document_screening_evaluations" in tables
        assert "document_screening_evidence" in tables
        assert versions == ["0006_document_screening"]
    finally:
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {EMPTY_DB}"))
        admin.dispose()
