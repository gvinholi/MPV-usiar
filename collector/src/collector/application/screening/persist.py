"""Persiste perfil e avaliação sem misturar com o motor de regras."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from collector.application.screening.errors import IncompatibleProfileError
from collector.application.screening.ports import ScreeningRepository
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.results import ScreeningEvaluation
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class PersistScreeningOutcome:
    evaluation_id: UUID
    created: bool


class PersistScreening:
    def __init__(
        self, repository: ScreeningRepository, *, clock: Clock = utc_now
    ) -> None:
        self._repository = repository
        self._clock = clock

    def persist_profile(self, profile: ScreeningProfile) -> ScreeningProfile:
        with self._repository.transaction():
            existing = self._repository.get_profile(profile.code, profile.version)
            if existing is None:
                if profile.id is None:
                    raise ValueError("perfil novo exige id")
                self._repository.insert_profile(profile, created_at=self._clock())
                return profile
            if existing.configuration() != profile.configuration():
                raise IncompatibleProfileError(
                    "perfil já persistido com configuração diferente"
                )
            return existing

    def persist_evaluation(
        self, evaluation: ScreeningEvaluation
    ) -> PersistScreeningOutcome:
        if evaluation.profile_id is None:
            raise ValueError("avaliação persistida exige profile_id")
        with self._repository.transaction():
            stored = self._repository.get_evaluation(
                evaluation.observation_id,
                evaluation.profile_id,
                evaluation.engine_version,
            )
            if stored is not None:
                return PersistScreeningOutcome(
                    evaluation_id=stored.id, created=False
                )
            self._repository.insert_evaluation(evaluation, created_at=self._clock())
            return PersistScreeningOutcome(
                evaluation_id=evaluation.id, created=True
            )

    def persist(
        self, profile: ScreeningProfile, evaluation: ScreeningEvaluation
    ) -> PersistScreeningOutcome:
        stored_profile = self.persist_profile(profile)
        to_save = (
            evaluation
            if evaluation.profile_id == stored_profile.id
            else replace(evaluation, profile_id=stored_profile.id)
        )
        return self.persist_evaluation(to_save)
