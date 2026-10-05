"""Persistência documental em memória: idempotência e histórico."""

from dataclasses import replace
from uuid import uuid4

from collector.application.document_screening.evaluate import EvaluateDocumentScreening
from collector.application.document_screening.persist import PersistDocumentScreening
from collector.application.screening import PersistScreening, usiar_v1
from collector.application.screening.profile import ScreeningProfile
from tests.application.document_screening.fakes import InMemoryDocumentScreeningRepository
from tests.application.document_screening.helpers import corpus_from_pages, screen_pages
from tests.application.screening.fakes import InMemoryScreeningRepository
from tests.application.screening.helpers import screen


def test_same_fingerprint_is_idempotent() -> None:
    profiles = InMemoryScreeningRepository()
    documents = InMemoryDocumentScreeningRepository()
    service = PersistDocumentScreening(documents, profiles)
    profile = service.persist_profile(usiar_v1())
    evaluation = replace(
        screen_pages("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=profile.id,
    )
    first = service.persist_evaluation(evaluation)
    second = service.persist_evaluation(evaluation)
    assert first.created is True
    assert second.created is False
    assert len(documents.evaluations) == 1


def test_new_member_hash_creates_new_evaluation() -> None:
    profiles = InMemoryScreeningRepository()
    documents = InMemoryDocumentScreeningRepository()
    service = PersistDocumentScreening(documents, profiles)
    profile = service.persist_profile(usiar_v1())
    first = replace(
        screen_pages(
            "Manutenção preventiva de aparelhos de ar condicionado.",
            source_sha256="aa" * 32,
        ),
        profile_id=profile.id,
    )
    second = replace(
        screen_pages(
            "Manutenção preventiva de aparelhos de ar condicionado.",
            source_sha256="bb" * 32,
        ),
        profile_id=profile.id,
        process_id=first.process_id,
    )
    service.persist_evaluation(first)
    service.persist_evaluation(second)
    stored = documents.list_evaluations_for_process(first.process_id)
    assert len(stored) == 2
    assert stored[0].document_set_fingerprint != stored[1].document_set_fingerprint


def test_profile_v2_creates_new_evaluation() -> None:
    profiles = InMemoryScreeningRepository()
    documents = InMemoryDocumentScreeningRepository()
    service = PersistDocumentScreening(documents, profiles)
    v1 = service.persist_profile(usiar_v1())
    v2 = service.persist_profile(
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
    process_id = uuid4()
    first = replace(
        screen_pages("Manutenção preventiva de aparelhos de ar condicionado."),
        process_id=process_id,
        profile_id=v1.id,
    )
    second = replace(
        screen_pages(
            "Manutenção preventiva de aparelhos de ar condicionado.",
            profile=v2,
        ),
        process_id=process_id,
        profile_id=v2.id,
        profile_version="v2",
    )
    service.persist_evaluation(first)
    service.persist_evaluation(second)
    assert len(documents.list_evaluations_for_process(process_id)) == 2


def test_evaluate_process_uses_loaded_corpus() -> None:
    documents = InMemoryDocumentScreeningRepository()
    corpus = corpus_from_pages(
        "Contratação de manutenção preventiva dos aparelhos de ar condicionado."
    )
    documents.corpora[corpus.process_id] = corpus
    result = EvaluateDocumentScreening(documents).evaluate_process(
        corpus.process_id, usiar_v1()
    )
    assert result.evidence
    assert result.process_id == corpus.process_id


def test_initial_screening_remains_in_its_store() -> None:
    screening_repo = InMemoryScreeningRepository()
    document_repo = InMemoryDocumentScreeningRepository()
    PersistScreening(screening_repo).persist_profile(usiar_v1())
    initial = replace(
        screen("Manutenção e fornecimento de aparelhos de ar condicionado."),
        profile_id=usiar_v1().id,
    )
    PersistScreening(screening_repo).persist_evaluation(initial)
    document = replace(
        screen_pages("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=usiar_v1().id,
        process_id=initial.process_id,
    )
    PersistDocumentScreening(document_repo, screening_repo).persist_evaluation(document)
    assert len(screening_repo.evaluations) == 1
    assert screening_repo.evaluations[0].reason_code.value == "MIXED_MAINTENANCE_SUPPLY"
    assert len(document_repo.evaluations) == 1
    assert document_repo.evaluations[0].reason_code.value == "DOCUMENT_RELEVANT_MAINTENANCE"
