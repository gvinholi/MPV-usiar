"""Fingerprint depende de conteúdo, perfil e engine. Não de UUID/timestamp."""

from collector.application.document_screening.fingerprint import document_set_fingerprint
from collector.application.document_screening.results import DOCUMENT_ENGINE_VERSION
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.profiles import usiar_v1


def _v2(profile=None) -> ScreeningProfile:
    base = profile or usiar_v1()
    return ScreeningProfile(
        id=None,
        code=base.code,
        name=base.name,
        version="v2",
        context_terms=base.context_terms,
        maintenance_terms=base.maintenance_terms,
        sanitization_terms=base.sanitization_terms,
        installation_terms=base.installation_terms,
        purchase_terms=base.purchase_terms,
        parts_terms=base.parts_terms,
    )


def test_same_members_different_order_same_fingerprint() -> None:
    profile = usiar_v1()
    first = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("aa" * 32, "bb" * 32))
    second = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("bb" * 32, "aa" * 32))
    assert first == second


def test_new_member_changes_fingerprint() -> None:
    profile = usiar_v1()
    base = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("aa" * 32,))
    extra = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("aa" * 32, "cc" * 32))
    assert base != extra


def test_changed_hash_changes_fingerprint() -> None:
    profile = usiar_v1()
    first = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("aa" * 32,))
    second = document_set_fingerprint(profile, DOCUMENT_ENGINE_VERSION, ("ab" + "a" * 62,))
    assert first != second


def test_profile_v2_changes_fingerprint() -> None:
    members = ("aa" * 32,)
    first = document_set_fingerprint(usiar_v1(), DOCUMENT_ENGINE_VERSION, members)
    second = document_set_fingerprint(_v2(), DOCUMENT_ENGINE_VERSION, members)
    assert first != second


def test_engine_v2_changes_fingerprint() -> None:
    profile = usiar_v1()
    first = document_set_fingerprint(profile, "1", ("aa" * 32,))
    second = document_set_fingerprint(profile, "2", ("aa" * 32,))
    assert first != second


def test_fingerprint_is_sha256_hex() -> None:
    digest = document_set_fingerprint(usiar_v1(), "1", ("aa" * 32,))
    assert len(digest) == 64
    assert int(digest, 16) >= 0
