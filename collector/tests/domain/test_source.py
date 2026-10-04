"""Identidade de fonte: Enum fechado, sem strings soltas."""

import pytest

from collector.domain import Source, SourceIdentity


def test_source_is_closed_enum() -> None:
    assert {item for item in Source} == {Source.PNCP, Source.RHS}
    assert Source.PNCP is not Source.RHS
    assert isinstance(Source.PNCP, Source)


def test_source_identity_uses_official_id() -> None:
    identity = SourceIdentity(source=Source.PNCP, official_id="  abc-123  ")

    assert identity.source is Source.PNCP
    assert identity.official_id == "abc-123"


def test_source_identity_requires_official_id() -> None:
    with pytest.raises(ValueError, match="id oficial"):
        SourceIdentity(source=Source.PNCP, official_id="   ")


def test_same_official_id_on_different_sources_are_distinct() -> None:
    pncp = SourceIdentity(source=Source.PNCP, official_id="123")
    rhs = SourceIdentity(source=Source.RHS, official_id="123")

    assert pncp != rhs
