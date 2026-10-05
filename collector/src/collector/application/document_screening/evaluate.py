"""Caso de uso: avaliar um processo ou um artefato por vez."""

from __future__ import annotations

from uuid import UUID

from collector.application.document_screening.engine import DocumentScreeningEngine
from collector.application.document_screening.ports import DocumentScreeningRepository
from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.screening.profile import ScreeningProfile


class EvaluateDocumentScreening:
    def __init__(
        self,
        repository: DocumentScreeningRepository,
        engine: DocumentScreeningEngine | None = None,
    ) -> None:
        self._repository = repository
        self._engine = engine or DocumentScreeningEngine()

    def evaluate_process(
        self, process_id: UUID, profile: ScreeningProfile
    ) -> DocumentScreeningEvaluation:
        with self._repository.transaction():
            corpus = self._repository.load_corpus(process_id)
        return self._engine.evaluate(profile, corpus, profile_id=profile.id)

    def evaluate_artifact(
        self, process_id: UUID, artifact_sha256: str, profile: ScreeningProfile
    ) -> DocumentScreeningEvaluation:
        with self._repository.transaction():
            corpus = self._repository.load_corpus_for_artifact(process_id, artifact_sha256)
        return self._engine.evaluate(profile, corpus, profile_id=profile.id)
