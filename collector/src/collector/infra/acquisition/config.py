"""Configuração do armazenamento de artefatos. Um único ponto de env."""

from __future__ import annotations

import os
from pathlib import Path

from collector.application.acquisition.policy import (
    DEFAULT_MAX_DOWNLOAD_BYTES,
    DocumentAcquisitionPolicy,
)

DEFAULT_ARTIFACT_STORAGE_PATH = Path("var/artifacts")


def artifact_storage_path() -> Path:
    raw = os.environ.get("ARTIFACT_STORAGE_PATH", "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_ARTIFACT_STORAGE_PATH


def document_acquisition_policy() -> DocumentAcquisitionPolicy:
    raw = os.environ.get("DOCUMENT_MAX_DOWNLOAD_BYTES", "").strip()
    if not raw:
        return DocumentAcquisitionPolicy()
    return DocumentAcquisitionPolicy(max_download_bytes=int(raw))
