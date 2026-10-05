"""Persistência e fila operacional em memória."""

from dataclasses import replace
from datetime import UTC, datetime

from collector.application.resolution.persist import PersistOperationalResolution
from collector.application.resolution.summarize import summarize_resolutions
from collector.domain import ScreeningStatus
from tests.application.resolution.fakes import InMemoryResolutionRepository
from tests.application.resolution.helpers import document_case, resolve
from tests.application.screening.helpers import screen


def test_same_inputs_are_idempotent() -> None:
    repo = InMemoryResolutionRepository()
    service = PersistOperationalResolution(repo)
    initial = replace(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=screen("x").profile_id,
    )
    # profile_id from usiar_v1
    from collector.application.screening import usiar_v1

    initial = replace(initial, profile_id=usiar_v1().id)
    resolution = resolve(initial, None)
    first = service.persist(resolution)
    second = service.persist(resolution)
    assert first.created is True
    assert second.created is False
    assert len(repo.resolutions) == 1


def test_new_document_creates_new_resolution() -> None:
    from collector.application.screening import usiar_v1

    repo = InMemoryResolutionRepository()
    service = PersistOperationalResolution(repo)
    initial = replace(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=usiar_v1().id,
    )
    first = resolve(initial, None)
    second = resolve(
        initial,
        document_case(
            "Contratação de manutenção preventiva dos aparelhos de ar condicionado.",
            process_id=initial.process_id,
            fingerprint="aa" * 32,
        ),
    )
    service.persist(first)
    service.persist(replace(second, profile_id=usiar_v1().id))
    stored = repo.list_resolutions_for_process(initial.process_id)
    assert len(stored) == 2
    assert repo.latest_resolution(initial.process_id).state is ScreeningStatus.CANDIDATE


def test_list_current_by_state() -> None:
    from collector.application.screening import usiar_v1

    repo = InMemoryResolutionRepository()
    service = PersistOperationalResolution(repo)
    early = datetime(2026, 10, 5, 1, tzinfo=UTC)
    late = datetime(2026, 10, 5, 2, tzinfo=UTC)
    first_initial = replace(
        screen("Aquisição de condicionadores de ar."),
        profile_id=usiar_v1().id,
    )
    second_initial = replace(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=usiar_v1().id,
    )
    discarded = replace(resolve(first_initial, None), resolved_at=early)
    candidate = replace(resolve(second_initial, None), resolved_at=late)
    service.persist(discarded)
    service.persist(candidate)
    current_candidates = repo.list_current_resolutions(state=ScreeningStatus.CANDIDATE)
    assert [item.state for item in current_candidates] == [ScreeningStatus.CANDIDATE]


def test_summary_recovery_and_downgrade() -> None:
    from collector.application.screening import usiar_v1

    discarded = replace(
        screen("Aquisição de condicionadores de ar."),
        profile_id=usiar_v1().id,
    )
    candidate = replace(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        profile_id=usiar_v1().id,
    )
    recovered = resolve(
        discarded,
        document_case(
            "Contratação de manutenção preventiva dos aparelhos de ar condicionado.",
            process_id=discarded.process_id,
        ),
    )
    downgraded = resolve(
        candidate,
        document_case(
            "Serviço de instalação de aparelhos de ar condicionado.",
            process_id=candidate.process_id,
        ),
    )
    summary = summarize_resolutions((recovered, downgraded))
    assert summary.recovered_from_initial_discard == 1
    assert summary.candidate_downgraded_to_discarded == 1
    assert summary.changed_state == 2
    assert summary.document_based == 2
