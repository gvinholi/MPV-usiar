"""Fingerprint da resolução: conteúdo lógico, não UUID/timestamp."""

from dataclasses import replace
from uuid import uuid4

from collector.application.resolution.fingerprint import (
    initial_input_fingerprint,
    resolution_fingerprint,
)
from collector.application.resolution.resolver import OperationalResolver
from tests.application.resolution.helpers import document_case, resolve
from tests.application.screening.helpers import screen


def test_same_inputs_same_fingerprint() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    document = document_case(
        "Contratação de manutenção preventiva dos aparelhos de ar condicionado.",
        process_id=initial.process_id,
        fingerprint="aa" * 32,
    )
    first = OperationalResolver().resolve(initial, document)
    second = OperationalResolver().resolve(initial, document)
    assert first.resolution_fingerprint == second.resolution_fingerprint
    assert first.resolution_fingerprint == resolution_fingerprint(initial, document)


def test_document_none_is_deterministic() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    first = resolve(initial, None)
    second = resolve(initial, None)
    assert first.resolution_fingerprint == second.resolution_fingerprint
    assert "NONE" != first.resolution_fingerprint


def test_different_document_fingerprint_changes_resolution() -> None:
    initial = screen("Regras para apresentação da proposta.")
    first = resolve(initial, document_case("Regras.", process_id=initial.process_id, fingerprint="aa" * 32))
    second = resolve(initial, document_case("Regras.", process_id=initial.process_id, fingerprint="bb" * 32))
    assert first.resolution_fingerprint != second.resolution_fingerprint


def test_different_initial_changes_fingerprint() -> None:
    first = resolve(screen("Manutenção preventiva de aparelhos de ar condicionado."), None)
    second = resolve(screen("Aquisição de condicionadores de ar."), None)
    assert first.resolution_fingerprint != second.resolution_fingerprint
    assert initial_input_fingerprint(screen("x")) != initial_input_fingerprint(
        screen("Manutenção preventiva de chillers.")
    )


def test_profile_version_changes_fingerprint() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    other = replace(initial, profile_version="v2")
    assert resolution_fingerprint(initial, None) != resolution_fingerprint(other, None)


def test_resolver_version_changes_fingerprint() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    assert resolution_fingerprint(initial, None, resolver_version="1") != resolution_fingerprint(
        initial, None, resolver_version="2"
    )


def test_evaluation_uuid_does_not_change_logical_fingerprint() -> None:
    initial = screen("Manutenção preventiva de aparelhos de ar condicionado.")
    clone = replace(initial, id=uuid4())
    assert initial_input_fingerprint(initial) == initial_input_fingerprint(clone)
    assert resolution_fingerprint(initial, None) == resolution_fingerprint(clone, None)
