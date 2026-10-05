"""Repositório documental em memória."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.document_screening.results import (
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
)
from collector.application.persistence.errors import PersistenceError
from collector.application.screening.results import ScreeningEvaluation


class InMemoryDocumentScreeningRepository:
    def __init__(self) -> None:
        self.corpora: dict[UUID, DocumentScreeningCorpus] = {}
        self.artifact_corpora: dict[tuple[UUID, str], DocumentScreeningCorpus] = {}
        self.evaluations: list[DocumentScreeningEvaluation] = []
        self.initial: list[ScreeningEvaluation] = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def load_corpus(self, process_id: UUID) -> DocumentScreeningCorpus:
        return self.corpora[process_id]

    def load_corpus_for_artifact(
        self, process_id: UUID, artifact_sha256: str
    ) -> DocumentScreeningCorpus:
        return self.artifact_corpora[(process_id, artifact_sha256)]

    def get_evaluation(
        self,
        process_id: UUID,
        profile_id: UUID,
        engine_version: str,
        document_set_fingerprint: str,
    ) -> DocumentScreeningEvaluation | None:
        for evaluation in self.evaluations:
            if (
                evaluation.process_id == process_id
                and evaluation.profile_id == profile_id
                and evaluation.engine_version == engine_version
                and evaluation.document_set_fingerprint == document_set_fingerprint
            ):
                return evaluation
        return None

    def insert_evaluation(
        self, evaluation: DocumentScreeningEvaluation, *, created_at: datetime
    ) -> None:
        if evaluation.profile_id is None:
            raise PersistenceError("avaliação documental persistida exige profile_id")
        self.evaluations.append(evaluation)

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[DocumentScreeningEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.process_id == process_id)

    def latest_initial_evaluation(
        self, process_id: UUID, profile_id: UUID
    ) -> ScreeningEvaluation | None:
        matches = [
            item
            for item in self.initial
            if item.process_id == process_id and item.profile_id == profile_id
        ]
        if not matches:
            return None
        return matches[-1]
