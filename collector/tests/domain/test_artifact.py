"""Identidade técnica do artefato não é identidade oficial."""

from uuid import uuid4

import pytest

from collector.domain import Artifact, FileType


def test_sha256_must_be_hex() -> None:
    with pytest.raises(ValueError, match="sha256"):
        Artifact(
            id=uuid4(),
            sha256="nao-e-hash",
            size_bytes=1,
            detected_type=FileType.PDF,
            storage_key="sha256/aa/bb/cc",
        )


def test_hash_algorithm_is_technical_sha256() -> None:
    digest = "a" * 64
    artifact = Artifact(
        id=uuid4(),
        sha256=digest,
        size_bytes=10,
        detected_type=FileType.ZIP,
        storage_key=f"sha256/aa/aa/{digest}",
    )
    assert artifact.hash_algorithm == "sha256"
    assert artifact.sha256 == digest
