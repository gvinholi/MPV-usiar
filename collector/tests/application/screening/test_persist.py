"""Persistência da triagem com repositório em memória."""

from dataclasses import replace
from uuid import uuid4

import pytest

from collector.application.screening import (
    IncompatibleProfileError,
    PersistScreening,
    usiar_v1,
)
from collector.application.screening.profile import ScreeningProfile
from tests.application.screening.fakes import InMemoryScreeningRepository
from tests.application.screening.helpers import screen


def test_same_observation_and_profile_is_idempotent() -> None:
    repository = InMemoryScreeningRepository()
    service = PersistScreening(repository)
    profile = service.persist_profile(usiar_v1())
    evaluation = replace(screen("Manutenção preventiva de chillers."), profile_id=profile.id)

    first = service.persist_evaluation(evaluation)
    second = service.persist_evaluation(evaluation)

    assert first.created is True
    assert second.created is False
    assert len(repository.evaluations) == 1


def test_same_observation_new_profile_version_creates_new_evaluation() -> None:
    repository = InMemoryScreeningRepository()
    service = PersistScreening(repository)
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
    observation_id = uuid4()
    process_id = uuid4()
    first = replace(
        screen("Manutenção preventiva de chillers."),
        process_id=process_id,
        observation_id=observation_id,
        profile_id=v1.id,
    )
    second = replace(
        screen("Manutenção preventiva de chillers.", replace(v1, version="v2", id=v2.id)),
        process_id=process_id,
        observation_id=observation_id,
        profile_id=v2.id,
        profile_version="v2",
    )
    service.persist_evaluation(first)
    service.persist_evaluation(second)

    stored = repository.list_evaluations_for_process(process_id)
    assert len(stored) == 2
    assert {item.profile_version for item in stored} == {"v1", "v2"}


def test_incompatible_profile_configuration_is_rejected() -> None:
    service = PersistScreening(InMemoryScreeningRepository())
    service.persist_profile(usiar_v1())
    changed = replace(usiar_v1(), context_terms=("outro",))
    with pytest.raises(IncompatibleProfileError):
        service.persist_profile(changed)
