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
        "artifacts",
        "document_artifacts",
        "artifact_archive_entries",
        "artifact_text_sources",
        "text_extractions",
        "text_extraction_pages",
        "auth_users",
        "auth_permissions",
        "auth_user_permissions",
        "auth_sessions",
        "auth_login_attempts",
        "auth_audit_events",
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
    assert "uq_artifacts_sha256" in names
    assert "uq_artifact_text_sources_artifact_path_sha" in names
    assert "uq_text_extractions_source_extractor_version" in names
    assert "uq_text_extraction_pages_extraction_page" in names
    assert "uq_auth_users_normalized_email" in names
    assert "uq_auth_sessions_verifier_digest" in names


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
    assert "fk_auth_user_permissions_user_id_auth_users" in names
    assert "fk_auth_user_permissions_permission_code_auth_permissions" in names
    assert "fk_auth_sessions_user_id_auth_users" in names
    assert "fk_auth_audit_events_subject_user_id_auth_users" in names
