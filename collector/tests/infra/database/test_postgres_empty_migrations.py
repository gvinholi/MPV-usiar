"""Migration limpa: banco vazio sobe 0001 → head."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

pytestmark = pytest.mark.postgres

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
EMPTY_DB = "usiar_mig_empty"


def test_alembic_upgrade_from_empty_database(postgres_url: str) -> None:
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {EMPTY_DB} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {EMPTY_DB}"))
    empty_url = postgres_url.rsplit("/", 1)[0] + f"/{EMPTY_DB}"
    engine = None
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
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars()
            )
        engine.dispose()
        assert "collection_rounds" in tables
        assert "screening_evaluations" in tables
        assert "process_documents" in tables
        assert "artifacts" in tables
        assert "text_extraction_pages" in tables
        assert "document_screening_evaluations" in tables
        assert "document_screening_evidence" in tables
        assert "operational_resolutions" in tables
        assert "human_reviews" in tables
        assert "auth_users" in tables
        assert "auth_sessions" in tables
        assert "auth_audit_events" in tables
        assert versions == ["0013_collection_leases"]

        command.downgrade(config, "0009_internal_auth")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO collection_rounds "
                    "(id,source,started_at,finished_at,status,pages_expected,"
                    "pages_processed,pages_with_error,records_collected,"
                    "unique_processes,candidates,selected,pending,discarded,"
                    "documents_found,errors,created_at) VALUES "
                    "(:round_id,'PNCP',now(),now(),'SUCCESS',0,0,0,0,0,0,0,0,0,0,0,now())"
                ),
                {"round_id": "11111111-1111-1111-1111-111111111111"},
            )
            connection.execute(
                text(
                    "INSERT INTO processes (id,created_at,updated_at) "
                    "VALUES (:process_id,now(),now())"
                ),
                {"process_id": "22222222-2222-2222-2222-222222222222"},
            )
            connection.execute(
                text(
                    "INSERT INTO process_observations "
                    "(id,process_id,round_id,source,official_url,created_at) VALUES "
                    "(:observation_id,:process_id,:round_id,'PNCP',:url,now())"
                ),
                {
                    "observation_id": "33333333-3333-3333-3333-333333333333",
                    "process_id": "22222222-2222-2222-2222-222222222222",
                    "round_id": "11111111-1111-1111-1111-111111111111",
                    "url": "https://example.gov.br/contratacao/42",
                },
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            migrated = connection.execute(
                text(
                    "SELECT notice_number, official_url "
                    "FROM process_observations WHERE id=:id"
                ),
                {"id": "33333333-3333-3333-3333-333333333333"},
            ).one()
            assert migrated == (None, "https://example.gov.br/contratacao/42")

        command.downgrade(config, "0008_human_reviews")
        with engine.connect() as connection:
            auth_tables = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE 'auth_%'"
                    )
                ).scalars()
            )
            assert auth_tables == set()
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "0008_human_reviews"
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            permissions = set(
                connection.execute(text("SELECT code FROM auth_permissions")).scalars()
            )
            assert permissions == {"dashboard:read", "reviews:write"}
            assert (
                connection.execute(text("SELECT count(*) FROM auth_users")).scalar_one()
                == 0
            )
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {EMPTY_DB} WITH (FORCE)"))
        admin.dispose()
