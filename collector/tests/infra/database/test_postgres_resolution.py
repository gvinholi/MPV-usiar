"""Resolução operacional contra PostgreSQL real."""

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
    OperationalResolver,
    PersistCollection,
    PersistDocumentAcquisition,
    PersistDocumentCatalog,
    PersistDocumentScreening,
    PersistOperationalResolution,
    PersistScreening,
    PersistTextExtraction,
    RetryPolicy,
    ScreeningEngine,
    usiar_v1,
)
from collector.application.resolution.fingerprint import resolution_fingerprint
from collector.domain import ScreeningStatus
from collector.infra.acquisition import LocalArtifactStorage
from collector.infra.database import (
    SqlAlchemyDocumentAcquisitionRepository,
    SqlAlchemyDocumentCatalogRepository,
    SqlAlchemyDocumentScreeningRepository,
    SqlAlchemyOperationalResolutionRepository,
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
CAPTURED = datetime(2026, 10, 5, 1, 0, tzinfo=UTC)
CANDIDATE_TEXT = (
    "Contratacao de empresa para execucao de manutencao preventiva e "
    "corretiva dos aparelhos de ar condicionado."
)


@pytest.fixture
def factories(migrated_engine, db_session: Session):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    return factory


def _catalog(document_persist, process_id, item):
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


def _seed(factories, persist_service, tmp_path: Path, *, official_id: str, sequential: int, description: str, page_text: str):
    document_persist = PersistDocumentCatalog(SqlAlchemyDocumentCatalogRepository(factories))
    acquisition_persist = PersistDocumentAcquisition(
        SqlAlchemyDocumentAcquisitionRepository(factories)
    )
    text_persist = PersistTextExtraction(SqlAlchemyTextExtractionRepository(factories))
    snapshot = process(official_id, description=description)
    persist_service.persist(collection_result(snapshot))
    document = _catalog(
        document_persist, snapshot.id, observed_document(sequential=sequential)
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
    return snapshot


def test_operational_table_exists(db_session: Session) -> None:
    names = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    assert "operational_resolutions" in names


def test_initial_only_and_latest_and_idempotency(
    persist_service: PersistCollection,
    factories,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot = _seed(
        factories,
        persist_service,
        tmp_path,
        official_id="RES-1",
        sequential=11,
        description="Manutencao preventiva de aparelhos de ar condicionado.",
        page_text=CANDIDATE_TEXT,
    )
    screening = PersistScreening(SqlAlchemyScreeningRepository(factories))
    profile = screening.persist_profile(usiar_v1())
    observation = db_session.execute(
        text("SELECT id, process_id FROM process_observations")
    ).one()
    initial = ScreeningEngine().evaluate(
        profile,
        description=snapshot.description,
        process_id=observation[1],
        observation_id=observation[0],
        profile_id=profile.id,
    )
    screening.persist_evaluation(initial)
    resolver = OperationalResolver()
    resolution = resolver.resolve(initial, None)
    service = PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factories))
    first = service.persist(resolution)
    second = service.persist(resolution)
    assert first.created is True
    assert second.created is False
    repo = SqlAlchemyOperationalResolutionRepository(factories)
    with repo.transaction():
        latest = repo.latest_resolution(snapshot.id, profile.id)
        queue = repo.list_current_resolutions(state=ScreeningStatus.CANDIDATE)
    assert latest is not None
    assert latest.state is ScreeningStatus.CANDIDATE
    assert latest.reason_code.value == "INITIAL_SCREENING_ONLY"
    assert latest.document_evaluation_id is None
    assert [item.process_id for item in queue] == [snapshot.id]
    assert db_session.execute(text("SELECT COUNT(*) FROM screening_evaluations")).scalar_one() == 1


def test_initial_plus_document_history_and_divergence(
    persist_service: PersistCollection,
    factories,
    db_session: Session,
    tmp_path: Path,
) -> None:
    snapshot = _seed(
        factories,
        persist_service,
        tmp_path,
        official_id="RES-2",
        sequential=12,
        description="Manutencao e fornecimento de aparelhos de ar condicionado.",
        page_text="Regras para apresentacao da proposta.",
    )
    screening = PersistScreening(SqlAlchemyScreeningRepository(factories))
    documents = PersistDocumentScreening(
        SqlAlchemyDocumentScreeningRepository(factories),
        SqlAlchemyScreeningRepository(factories),
    )
    profile = screening.persist_profile(usiar_v1())
    observation = db_session.execute(
        text("SELECT id, process_id FROM process_observations")
    ).one()
    initial = ScreeningEngine().evaluate(
        profile,
        description=snapshot.description,
        process_id=observation[1],
        observation_id=observation[0],
        profile_id=profile.id,
    )
    screening.persist_evaluation(initial)
    document_repo = SqlAlchemyDocumentScreeningRepository(factories)
    document = EvaluateDocumentScreening(document_repo).evaluate_process(snapshot.id, profile)
    documents.persist_evaluation(document)
    resolver = OperationalResolver()
    only_initial = resolver.resolve(initial, None)
    with_document = resolver.resolve(initial, document)
    service = PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factories))
    service.persist(only_initial)
    service.persist(with_document)
    assert db_session.execute(text("SELECT COUNT(*) FROM operational_resolutions")).scalar_one() == 2
    assert db_session.execute(text("SELECT COUNT(*) FROM screening_evaluations")).scalar_one() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_screening_evaluations")).scalar_one() == 1
    repo = SqlAlchemyOperationalResolutionRepository(factories)
    with repo.transaction():
        latest = repo.latest_resolution(snapshot.id)
        history = repo.list_resolutions_for_process(snapshot.id)
    assert latest.state is ScreeningStatus.PENDING
    assert latest.reason_code.value == "DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE"
    assert latest.state_diverged is False
    assert latest.reason_diverged is True
    assert latest.initial_evaluation_id == initial.id
    assert latest.document_evaluation_id == document.id
    assert len(history) == 2
    v2 = resolver.resolve(initial, document)
    from dataclasses import replace

    v2 = replace(
        v2,
        resolver_engine_version="2",
        resolution_fingerprint=resolution_fingerprint(initial, document, resolver_version="2"),
    )
    service.persist(v2)
    assert db_session.execute(text("SELECT COUNT(*) FROM operational_resolutions")).scalar_one() == 3
