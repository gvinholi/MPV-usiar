"""Resolução de identidade persistente — sem banco."""

from uuid import uuid4

import pytest

from collector.application.persistence import (
    CreateProcess,
    IdentityConflict,
    ReuseProcess,
    resolve_identities,
)
from collector.domain import Source, SourceIdentity


def _id(official_id: str, source: Source = Source.PNCP) -> SourceIdentity:
    return SourceIdentity(source=source, official_id=official_id)


def test_no_existing_identity_creates_process() -> None:
    identities = (_id("123"),)
    decision = resolve_identities(identities, {})

    assert isinstance(decision, CreateProcess)
    assert decision.identities == identities


def test_existing_identity_reuses_process() -> None:
    process_id = uuid4()
    identities = (_id("123"),)
    decision = resolve_identities(identities, {_id("123"): process_id})

    assert isinstance(decision, ReuseProcess)
    assert decision.process_id == process_id
    assert decision.new_identities == ()


def test_additional_identity_is_attached_to_same_process() -> None:
    process_id = uuid4()
    identities = (_id("123"), _id("XYZ", Source.RHS))
    decision = resolve_identities(identities, {_id("123"): process_id})

    assert isinstance(decision, ReuseProcess)
    assert decision.process_id == process_id
    assert decision.new_identities == (_id("XYZ", Source.RHS),)


def test_identities_pointing_to_two_processes_conflict() -> None:
    left = uuid4()
    right = uuid4()
    identities = (_id("AAA"), _id("BBB"))
    decision = resolve_identities(
        identities, {_id("AAA"): left, _id("BBB"): right}
    )

    assert isinstance(decision, IdentityConflict)
    assert set(decision.process_ids) == {left, right}


def test_empty_identities_are_rejected() -> None:
    with pytest.raises(ValueError, match="sem identidade"):
        resolve_identities((), {})
