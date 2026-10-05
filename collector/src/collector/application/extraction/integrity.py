"""Integridade do blob armazenado. SHA-256 técnico, não versão oficial."""

from __future__ import annotations

import hashlib

from collector.application.acquisition.ports import ArtifactStorage
from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.reasons import ExtractionReason
from collector.domain.artifact import Artifact


def verify_artifact_blob(storage: ArtifactStorage, artifact: Artifact) -> None:
    if not storage.exists(artifact.sha256):
        raise ExtractionError(
            "artefato não encontrado no storage",
            reason=ExtractionReason.ARTIFACT_NOT_FOUND,
        )
    hasher = hashlib.sha256()
    try:
        with storage.open(artifact.storage_key) as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError as exc:
        raise ExtractionError(
            "falha ao ler artefato do storage",
            reason=ExtractionReason.STORAGE_READ_ERROR,
        ) from exc
    digest = hasher.hexdigest()
    if digest != artifact.sha256:
        raise ExtractionError(
            "SHA-256 do storage diverge do artefato persistido",
            reason=ExtractionReason.ARTIFACT_INTEGRITY_MISMATCH,
        )
