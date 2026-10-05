"""Invariantes do resolver: sem SELECTED/CONFIRMED e falhas explícitas."""

import pytest
from dataclasses import replace

from collector.application.resolution.errors import (
    InitialScreeningRequiredError,
    ProcessMismatchError,
    ProfileMismatchError,
)
from collector.application.resolution.resolver import OperationalResolver
from collector.domain import ScreeningStatus
from tests.application.document_screening.helpers import screen_pages
from tests.application.resolution.helpers import document_case, resolve
from tests.application.screening.helpers import screen


def test_never_returns_selected_or_confirmed() -> None:
    cases = [
        resolve(screen("Manutenção preventiva de aparelhos de ar condicionado."), None),
        resolve(screen("Aquisição de condicionadores de ar."), None),
        resolve(
            screen("Aquisição de condicionadores de ar."),
            document_case("Contratação de manutenção preventiva dos aparelhos de ar condicionado."),
        ),
        resolve(
            screen("Manutenção preventiva de aparelhos de ar condicionado."),
            document_case("Serviço de instalação de aparelhos de ar condicionado."),
        ),
        resolve(
            screen("Manutenção preventiva de aparelhos de ar condicionado."),
            document_case("Regras para apresentação da proposta."),
        ),
    ]
    forbidden = {ScreeningStatus.SELECTED, ScreeningStatus.CONFIRMED}
    assert [item.state for item in cases if item.state in forbidden] == []


def test_positive_document_never_discarded() -> None:
    result = resolve(
        screen("Aquisição de condicionadores de ar."),
        document_case("Higienização de aparelhos de ar condicionado."),
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.state is not ScreeningStatus.DISCARDED


def test_non_decisive_never_discarded() -> None:
    result = resolve(
        screen("Aquisição de condicionadores de ar."),
        document_case("Regras para apresentação da proposta."),
    )
    assert result.state is ScreeningStatus.PENDING


def test_missing_initial_fails() -> None:
    document = screen_pages("Manutenção preventiva de aparelhos de ar condicionado.")
    with pytest.raises(InitialScreeningRequiredError, match="INITIAL_SCREENING_REQUIRED"):
        OperationalResolver().resolve(None, document)


def test_process_mismatch_fails() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    document = screen_pages("Manutenção preventiva de aparelhos de ar condicionado.")
    with pytest.raises(ProcessMismatchError):
        OperationalResolver().resolve(initial, document)


def test_profile_mismatch_fails() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    document = replace(
        screen_pages("Manutenção preventiva de aparelhos de ar condicionado."),
        process_id=initial.process_id,
        profile_code="OUTRO",
        profile_version="v1",
    )
    with pytest.raises(ProfileMismatchError):
        OperationalResolver().resolve(initial, document)
