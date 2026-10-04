"""Repositório de triagem em memória."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from collector.application.persistence.errors import PersistenceError
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.results import ScreeningEvaluation


class InMemoryScreeningRepository:
    def __init__(self) -> None:
        self.profiles: dict[tuple[str, str], ScreeningProfile] = {}
        self.evaluations: list[ScreeningEvaluation] = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def get_profile(self, code: str, version: str) -> ScreeningProfile | None:
        return self.profiles.get((code, version))

    def insert_profile(self, profile: ScreeningProfile, *, created_at: datetime) -> None:
        key = (profile.code, profile.version)
        if key in self.profiles:
            raise PersistenceError("perfil duplicado")
        self.profiles[key] = profile

    def get_evaluation(
        self,
        observation_id: UUID,
        profile_id: UUID,
        engine_version: str,
    ) -> ScreeningEvaluation | None:
        for evaluation in self.evaluations:
            if (
                evaluation.observation_id == observation_id
                and evaluation.profile_id == profile_id
                and evaluation.engine_version == engine_version
            ):
                return evaluation
        return None

    def insert_evaluation(
        self, evaluation: ScreeningEvaluation, *, created_at: datetime
    ) -> None:
        self.evaluations.append(evaluation)

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[ScreeningEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.process_id == process_id)
