"""Persistência da triagem documental contra PostgreSQL real."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from collector.application import (
    AcquireDocumentArtifact,
    CatalogProcessDocuments,
    DocumentAcquisitionPolicy,
    DocumentQuery,
    EvaluateDocumentScreening,
    ExtractArtifactText,
    PersistCollection,
    PersistDocumentAcquisition,
    PersistDocumentCatalog,
    PersistDocumentScreening,
    PersistScreening,
    PersistTextExtraction,
    RetryPolicy,
    ScreeningEngine,
    compare_screenings,
    usiar_v1,
)
from collector.application.screening.profile import ScreeningProfile
from collector.domain import ScreeningStatus
from collector.infra.acquisition import LocalArtifactStorage
from collector.infra.database import (
    SqlAlchemyDocumentAcquisitionRepository,
    SqlAlchemyDocumentCatalogRepository,
    SqlAlchemyDocumentScreeningRepository,
    SqlAlchemyScreeningRepository,
    SqlAlchemyTextExtractionRepository,
)
from collector.infra.extraction import PypdfTextExtractor
from collector.infra.pncp import PncpDocumentMapper
from tests.application.acquisition.fakes import FakeDownloader
from tests.application.documents.fakes import FakeDocumentFetcher
from tests.application.extraction.pdf_fixtures import text_pdf
from tests.application.persistence.factories import collection_result, process
from tests.application.publications.fakes import recording_waiter
from tests.infra.pncp.document_fixtures import observed_document

pytestmark = pytest.mark.postgres
CAPTURED = datetime(2026, 10, 4, 23, 0, tzinfo=UTC)
CANDIDATE_TEXT = (
    "Contratacao de empresa para execucao de manutencao preventiva e "
    "corretiva dos aparelhos de ar condicionado."
)


@pytest.fixture
def document_persist(migrated_engine, db_session: Session) -> PersistDocumentCatalog:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentCatalog(SqlAlchemyDocumentCatalogRepository(factory))


@pytest.fixture
def acquisition_persist(
    migrated_engine, db_session: Session
) -> PersistDocumentAcquisition:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentAcquisition(SqlAlchemyDocumentAcquisitionRepository(factory))


@pytest.fixture
def text_persist(migrated_engine, db_session: Session) -> PersistTextExtraction:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistTextExtraction(SqlAlchemyTextExtractionRepository(factory))


@pytest.fixture
def screening_service(migrated_engine, db_session: Session) -> PersistScreening:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistScreening(SqlAlchemyScreeningRepository(factory))


@pytest.fixture
def document_screening_service(
    migrated_engine, db_session: Session
) -> PersistDocumentScreening:
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return PersistDocumentScreening(
        SqlAlchemyDocumentScreeningRepository(factory),
        SqlAlchemyScreeningRepository(factory),
    )


@pytest.fixture
def document_screening_repo(migrated_engine, db_session: Session):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return SqlAlchemyDocumentScreeningRepository(factory)


def _catalog_document(document_persist, process_id, item):
    _, waiter = recording_waiter()
    result = CatalogProcessDocuments(
        FakeDocumentFetcher([item]),
        PncpDocumentMapper(),
        retry_policy=RetryPolicy(max_attempts=1),
        waiter=waiter,
        clock=lambda: CAPTURED,
        new_id=uuid4,
    ).catalog(
        DocumentQuery(
            process_id=process_id,
            cnpj=str(item["cnpj"]),
            year=int(item["anoCompra"]),
            sequential=int(item["sequencialCompra"]),
        )
    )
    document_persist.persist(result)
    return result.documents[0]


def _seed_extracted_process(
    persist_service,
    document_persist,
    acquisition_persist,
    text_persist,
    tmp_path: Path,
    *,
    official_id: str,
    page_text: str,
    description: str,
    sequential: int = 1,
):
    snapshot = process(official_id, description=description)
    persist_service.persist(collection_result(snapshot))
    document = _catalog_document(
        document_persist,
        snapshot.id,
        observed_document(sequential=sequential),
    )
    storage = LocalArtifactStorage(tmp_path)
    acquired = AcquireDocumentArtifact(
        FakeDownloader(text_pdf(page_text)),
        storage,
        policy=DocumentAcquisitionPolicy(max_download_bytes=1024 * 1024),
        clock=lambda: CAPTURED,
    ).acquire(document)
    acquisition_persist.persist(acquired)
    text_persist.persist(
        ExtractArtifactText(storage, PypdfTextExtractor(), clock=lambda: CAPTURED).extract(
            acquired.artifact
        )
    )
    return snapshot, acquired.artifact.sha256


def test_document_screening_tables_exist(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert {
        "document_screening_evaluations",
        "document_screening_evidence",
        "screening_evaluations",
    }.issubset(names)


def test_persist_document_evaluation_and_evidence(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    screening_service: PersistScreening,
    document_screening_service: PersistDocumentScreening,
    document_screening_repo: SqlAlchemyDocumentScreeningRepository,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot, _sha = _seed_extracted_process(
        persist_service,
        document_persist,
        acquisition_persist,
        text_persist,
        tmp_path,
        official_id="DOC-SCR-1",
        page_text=CANDIDATE_TEXT,
        description="Manutencao e fornecimento de aparelhos de ar condicionado.",
    )
    profile = screening_service.persist_profile(usiar_v1())
    row = db_session.execute(
        text("SELECT id, process_id FROM process_observations")
    ).one()
    initial = ScreeningEngine().evaluate(
        profile,
        description=snapshot.description,
        process_id=row[1],
        observation_id=row[0],
        profile_id=profile.id,
    )
    screening_service.persist_evaluation(initial)
    evaluation = EvaluateDocumentScreening(document_screening_repo).evaluate_process(
        snapshot.id, profile
    )
    outcome = document_screening_service.persist_evaluation(evaluation)
    assert outcome.created is True
    assert evaluation.state is ScreeningStatus.CANDIDATE
    states = db_session.execute(
        text("SELECT state, reason_code FROM document_screening_evaluations")
    ).all()
    assert states == [("CANDIDATE", "DOCUMENT_RELEVANT_MAINTENANCE")]
    evidence_count = db_session.execute(
        text("SELECT COUNT(*) FROM document_screening_evidence")
    ).scalar_one()
    assert evidence_count >= 2
    snippet = db_session.execute(
        text("SELECT context_snippet, page_number FROM document_screening_evidence LIMIT 1")
    ).one()
    assert snippet[1] == 1
    assert snippet[0]
    initial_count = db_session.execute(
        text("SELECT COUNT(*) FROM screening_evaluations")
    ).scalar_one()
    assert initial_count == 1
    initial_state = db_session.execute(
        text("SELECT state, reason_code FROM screening_evaluations")
    ).one()
    assert initial_state == ("PENDING", "MIXED_MAINTENANCE_SUPPLY")


def test_same_fingerprint_is_idempotent(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    screening_service: PersistScreening,
    document_screening_service: PersistDocumentScreening,
    document_screening_repo: SqlAlchemyDocumentScreeningRepository,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot, _sha = _seed_extracted_process(
        persist_service,
        document_persist,
        acquisition_persist,
        text_persist,
        tmp_path,
        official_id="DOC-SCR-2",
        page_text=CANDIDATE_TEXT,
        description="x",
        sequential=2,
    )
    profile = screening_service.persist_profile(usiar_v1())
    evaluation = EvaluateDocumentScreening(document_screening_repo).evaluate_process(
        snapshot.id, profile
    )
    document_screening_service.persist_evaluation(evaluation)
    document_screening_service.persist_evaluation(evaluation)
    assert (
        db_session.execute(text("SELECT COUNT(*) FROM document_screening_evaluations")).scalar_one()
        == 1
    )


def test_new_content_and_profile_version_keep_history(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    screening_service: PersistScreening,
    document_screening_service: PersistDocumentScreening,
    document_screening_repo: SqlAlchemyDocumentScreeningRepository,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot, _sha = _seed_extracted_process(
        persist_service,
        document_persist,
        acquisition_persist,
        text_persist,
        tmp_path,
        official_id="DOC-SCR-3",
        page_text=CANDIDATE_TEXT,
        description="x",
        sequential=3,
    )
    v1 = screening_service.persist_profile(usiar_v1())
    first = EvaluateDocumentScreening(document_screening_repo).evaluate_process(
        snapshot.id, v1
    )
    document_screening_service.persist_evaluation(first)
    v2 = screening_service.persist_profile(
        ScreeningProfile(
            id=uuid4(),
            code="USIAR",
            name=v1.name,
            version="v2",
            context_terms=v1.context_terms,
            maintenance_terms=v1.maintenance_terms,
            sanitization_terms=v1.sanitization_terms,
            installation_terms=v1.installation_terms,
            purchase_terms=v1.purchase_terms,
            parts_terms=v1.parts_terms,
        )
    )
    second = EvaluateDocumentScreening(document_screening_repo).evaluate_process(
        snapshot.id, v2
    )
    document_screening_service.persist_evaluation(second)
    versions = set(
        db_session.execute(
            text(
                "SELECT p.version FROM document_screening_evaluations e "
                "JOIN screening_profiles p ON p.id = e.profile_id"
            )
        ).scalars()
    )
    assert versions == {"v1", "v2"}
    fingerprints = set(
        db_session.execute(
            text("SELECT document_set_fingerprint FROM document_screening_evaluations")
        ).scalars()
    )
    assert len(fingerprints) == 2


def test_divergence_is_queryable(
    persist_service: PersistCollection,
    document_persist: PersistDocumentCatalog,
    acquisition_persist: PersistDocumentAcquisition,
    text_persist: PersistTextExtraction,
    screening_service: PersistScreening,
    document_screening_service: PersistDocumentScreening,
    document_screening_repo: SqlAlchemyDocumentScreeningRepository,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot, _sha = _seed_extracted_process(
        persist_service,
        document_persist,
        acquisition_persist,
        text_persist,
        tmp_path,
        official_id="DOC-SCR-4",
        page_text=CANDIDATE_TEXT,
        description="Manutencao e fornecimento de aparelhos de ar condicionado.",
        sequential=4,
    )
    profile = screening_service.persist_profile(usiar_v1())
    observation = db_session.execute(
        text("SELECT id, process_id FROM process_observations")
    ).one()
    screening_service.persist_evaluation(
        ScreeningEngine().evaluate(
            profile,
            description=snapshot.description,
            process_id=observation[1],
            observation_id=observation[0],
            profile_id=profile.id,
        )
    )
    document = EvaluateDocumentScreening(document_screening_repo).evaluate_process(
        snapshot.id, profile
    )
    document_screening_service.persist_evaluation(document)
    with document_screening_repo.transaction():
        initial = document_screening_repo.latest_initial_evaluation(snapshot.id, profile.id)
        stored = document_screening_repo.list_evaluations_for_process(snapshot.id)
    comparison = compare_screenings(initial, stored[0])
    assert comparison.diverged is True
    assert comparison.initial_state is ScreeningStatus.PENDING
    assert comparison.document_state is ScreeningStatus.CANDIDATE
