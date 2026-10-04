"""Porta de persistência da triagem. Sem SQLAlchemy."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.results import ScreeningEvaluation


class ScreeningRepository(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def get_profile(self, code: str, version: str) -> ScreeningProfile | None: ...

    def insert_profile(self, profile: ScreeningProfile, *, created_at: datetime) -> None: ...

    def get_evaluation(
        self,
        observation_id: UUID,
        profile_id: UUID,
        engine_version: str,
    ) -> ScreeningEvaluation | None: ...

    def insert_evaluation(
        self, evaluation: ScreeningEvaluation, *, created_at: datetime
    ) -> None: ...

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[ScreeningEvaluation, ...]: ...
