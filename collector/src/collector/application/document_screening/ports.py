"""Portas da triagem documental. Sem SQLAlchemy."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.document_screening.results import (
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
)
from collector.application.screening.results import ScreeningEvaluation


class DocumentScreeningRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def load_corpus(self, process_id: UUID) -> DocumentScreeningCorpus: ...

    def load_corpus_for_artifact(
        self, process_id: UUID, artifact_sha256: str
    ) -> DocumentScreeningCorpus: ...

    def get_evaluation(
        self,
        process_id: UUID,
        profile_id: UUID,
        engine_version: str,
        document_set_fingerprint: str,
    ) -> DocumentScreeningEvaluation | None: ...

    def insert_evaluation(
        self, evaluation: DocumentScreeningEvaluation, *, created_at: datetime
    ) -> None: ...

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[DocumentScreeningEvaluation, ...]: ...

    def latest_initial_evaluation(
        self, process_id: UUID, profile_id: UUID
    ) -> ScreeningEvaluation | None: ...
