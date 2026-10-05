"""Migration sobe e as constraints existem no PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres


def test_expected_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {
        "collection_rounds",
        "collection_modality_outcomes",
        "processes",
        "source_identities",
        "process_observations",
        "screening_profiles",
        "screening_evaluations",
        "screening_evidence",
        "process_documents",
        "document_catalog_queries",
        "document_observations",
    }.issubset(names)
    assert "licitacoes" not in names


def test_unique_constraints_exist(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE constraint_type = 'UNIQUE' AND table_schema = 'public'"
        )
    ).scalars()
    names = set(rows)
    assert "uq_source_identities_source_official" in names
    assert "uq_modality_outcomes_round_code" in names
    assert "uq_process_observations_round_process" in names
    assert "uq_screening_profiles_code_version" in names
    assert "uq_screening_evaluations_observation_profile_engine" in names
    assert "uq_process_documents_source_official" in names
    assert "uq_document_observations_query_document" in names


def test_foreign_keys_exist(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public'"
        )
    ).scalars()
    names = set(rows)
    assert "fk_source_identities_process_id_processes" in names
    assert "fk_process_observations_process_id_processes" in names
    assert "fk_process_observations_round_id_collection_rounds" in names
    assert "fk_collection_modality_outcomes_round_id_collection_rounds" in names
