"""Persiste aquisição e artefato. Sem HTTP e sem filesystem."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from collector.application.acquisition.ports import DocumentAcquisitionRepository
from collector.application.acquisition.results import DocumentAcquisitionResult
from collector.domain.artifact import Artifact
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class PersistAcquisitionOutcome:
    acquisition_id: UUID
    artifact_id: UUID | None
    artifact_created: bool
    acquisition_created: bool


class PersistDocumentAcquisition:
    def __init__(
        self,
        repository: DocumentAcquisitionRepository,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def persist(self, result: DocumentAcquisitionResult) -> PersistAcquisitionOutcome:
        with self._repository.transaction():
            now = result.acquired_at or self._clock()
            artifact_created = False
            stored: Artifact | None = None
            if result.artifact is not None:
                found = self._repository.find_artifact_by_sha256(result.artifact.sha256)
                if found is None:
                    self._repository.insert_artifact(result.artifact, created_at=now)
                    stored = result.artifact
                    artifact_created = True
                    if result.archive is not None and result.archive.entries:
                        self._repository.insert_archive_entries(
                            result.artifact.id,
                            result.archive.entries,
                            created_at=now,
                        )
                else:
                    stored = found
                    if (
                        result.archive is not None
                        and result.archive.entries
                        and not self._repository.has_archive_entries(found.id)
                    ):
                        self._repository.insert_archive_entries(
                            found.id,
                            result.archive.entries,
                            created_at=now,
                        )
            persisted = result if stored is None or stored is result.artifact else _with_artifact(
                result, stored
            )
            self._repository.insert_acquisition(persisted, created_at=now)
            return PersistAcquisitionOutcome(
                acquisition_id=result.acquisition_id,
                artifact_id=None if stored is None else stored.id,
                artifact_created=artifact_created,
                acquisition_created=True,
            )


def _with_artifact(result: DocumentAcquisitionResult, artifact: Artifact) -> DocumentAcquisitionResult:
    from dataclasses import replace

    return replace(result, artifact=artifact)
