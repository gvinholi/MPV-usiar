"""Persiste avaliação documental sem tocar na triagem inicial."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from collector.application.document_screening.ports import DocumentScreeningRepository
from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.screening.errors import IncompatibleProfileError
from collector.application.screening.ports import ScreeningRepository
from collector.application.screening.profile import ScreeningProfile
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class PersistDocumentScreeningOutcome:
    evaluation_id: UUID
    created: bool


class PersistDocumentScreening:
    def __init__(
        self,
        repository: DocumentScreeningRepository,
        profile_repository: ScreeningRepository,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._profiles = profile_repository
        self._clock = clock

    def persist_profile(self, profile: ScreeningProfile) -> ScreeningProfile:
        with self._profiles.transaction():
            existing = self._profiles.get_profile(profile.code, profile.version)
            if existing is None:
                if profile.id is None:
                    raise ValueError("perfil novo exige id")
                self._profiles.insert_profile(profile, created_at=self._clock())
                return profile
            if existing.configuration() != profile.configuration():
                raise IncompatibleProfileError(
                    "perfil já persistido com configuração diferente"
                )
            return existing

    def persist_evaluation(
        self, evaluation: DocumentScreeningEvaluation
    ) -> PersistDocumentScreeningOutcome:
        if evaluation.profile_id is None:
            raise ValueError("avaliação documental persistida exige profile_id")
        with self._repository.transaction():
            stored = self._repository.get_evaluation(
                evaluation.process_id,
                evaluation.profile_id,
                evaluation.engine_version,
                evaluation.document_set_fingerprint,
            )
            if stored is not None:
                return PersistDocumentScreeningOutcome(
                    evaluation_id=stored.id, created=False
                )
            self._repository.insert_evaluation(evaluation, created_at=self._clock())
            return PersistDocumentScreeningOutcome(
                evaluation_id=evaluation.id, created=True
            )

    def persist(
        self, profile: ScreeningProfile, evaluation: DocumentScreeningEvaluation
    ) -> PersistDocumentScreeningOutcome:
        stored_profile = self.persist_profile(profile)
        to_save = (
            evaluation
            if evaluation.profile_id == stored_profile.id
            else replace(evaluation, profile_id=stored_profile.id)
        )
        return self.persist_evaluation(to_save)
