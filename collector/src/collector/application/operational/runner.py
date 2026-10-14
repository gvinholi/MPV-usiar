"""Composição do fluxo PNCP -> PostgreSQL -> triagem -> resolução inicial."""

from __future__ import annotations

import json
import logging

from collector.application.collection import CollectionOrchestrator, CollectionRequest
from collector.application.persistence import PersistCollection
from collector.application.resolution import (
    OperationalResolver,
    PersistOperationalResolution,
)
from collector.application.screening import (
    PersistScreening,
    ScreeningEngine,
    ScreeningProfile,
)
from collector.domain import ScreeningStatus

from .models import OperationalRunSummary, ScreeningMetrics
from .errors import OperationalRunAlreadyRunningError
from .ports import (
    OperationalRunLock,
    OperationalRunRepository,
    UnlockedOperationalRunLock,
)

Logger = logging.Logger


class OperationalCollectionRunner:
    def __init__(
        self,
        collector: CollectionOrchestrator,
        collection_persistence: PersistCollection,
        screening_persistence: PersistScreening,
        resolution_persistence: PersistOperationalResolution,
        operational_repository: OperationalRunRepository,
        *,
        screening_engine: ScreeningEngine | None = None,
        resolver: OperationalResolver | None = None,
        run_lock: OperationalRunLock | None = None,
        logger: Logger | None = None,
    ) -> None:
        self._collector = collector
        self._collection_persistence = collection_persistence
        self._screening_persistence = screening_persistence
        self._resolution_persistence = resolution_persistence
        self._operational_repository = operational_repository
        self._screening_engine = screening_engine or ScreeningEngine()
        self._resolver = resolver or OperationalResolver()
        self._run_lock = run_lock or UnlockedOperationalRunLock()
        self._logger = logger or logging.getLogger(__name__)

    def run(
        self, request: CollectionRequest, profile: ScreeningProfile
    ) -> OperationalRunSummary:
        with self._run_lock.acquire() as acquired:
            if not acquired:
                self._event("collection_skipped", reason="already_running")
                raise OperationalRunAlreadyRunningError(
                    "outra rodada operacional já está em execução"
                )
            return self._run_locked(request, profile)

    def _run_locked(
        self, request: CollectionRequest, profile: ScreeningProfile
    ) -> OperationalRunSummary:
        self._event(
            "collection_started",
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            uf=request.uf,
            modalities=list(request.modality_codes),
            profile=profile.identity,
        )
        result = self._collector.collect(request)
        round_id = result.collection_round.id
        self._event(
            "collection_finished",
            round_id=str(round_id),
            status=result.collection_round.status.value,
            records_collected=result.records_received,
            unique_processes=result.consolidation.unique_processes,
            errors=len(result.errors),
            pages_processed=result.collection_round.metrics.pages_processed,
            page_errors=result.collection_round.metrics.pages_with_error,
        )

        persisted = self._collection_persistence.persist(result)
        stored_profile = self._screening_persistence.persist_profile(profile)
        observations = self._operational_repository.list_round_observations(round_id)

        counts = {
            ScreeningStatus.CANDIDATE: 0,
            ScreeningStatus.PENDING: 0,
            ScreeningStatus.DISCARDED: 0,
        }
        evaluations_created = 0
        resolutions_created = 0
        for observation in observations:
            evaluation = self._screening_engine.evaluate(
                stored_profile,
                description=observation.description,
                process_id=observation.process_id,
                observation_id=observation.observation_id,
                profile_id=stored_profile.id,
            )
            screening_outcome = self._screening_persistence.persist_evaluation(
                evaluation
            )
            evaluations_created += int(screening_outcome.created)
            stored_evaluation = screening_outcome.evaluation
            resolution = self._resolver.resolve(stored_evaluation, None)
            resolution_outcome = self._resolution_persistence.persist(resolution)
            resolutions_created += int(resolution_outcome.created)
            counts[stored_evaluation.state] += 1

        metrics = ScreeningMetrics(
            candidates=counts[ScreeningStatus.CANDIDATE],
            pending=counts[ScreeningStatus.PENDING],
            discarded=counts[ScreeningStatus.DISCARDED],
        )
        if metrics.evaluated != len(observations):
            raise RuntimeError("inconsistent operational screening metrics")
        self._operational_repository.update_screening_metrics(round_id, metrics)

        summary = OperationalRunSummary(
            round_id=round_id,
            status=result.collection_round.status.value,
            requested_modalities=result.requested_modalities,
            completed_modalities=result.completed_modalities,
            incomplete_modalities=result.incomplete_modalities,
            records_collected=result.records_received,
            processes_mapped=result.processes_mapped,
            unique_processes=result.consolidation.unique_processes,
            processes_created=persisted.processes_created,
            observations_created=persisted.observations_created,
            evaluations_created=evaluations_created,
            resolutions_created=resolutions_created,
            candidates=metrics.candidates,
            pending=metrics.pending,
            discarded=metrics.discarded,
            errors=len(result.errors),
            pages_processed=result.collection_round.metrics.pages_processed,
            page_errors=result.collection_round.metrics.pages_with_error,
        )
        self._event("operational_run_finished", **summary.as_dict())
        return summary

    def _event(self, event: str, **fields: object) -> None:
        self._logger.info(
            json.dumps({"event": event, **fields}, ensure_ascii=False, sort_keys=True)
        )
