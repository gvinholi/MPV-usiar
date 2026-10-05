"""Adaptadores de aquisição de binários."""

from collector.infra.acquisition.client import HttpxBinaryDownloader
from collector.infra.acquisition.config import (
    artifact_storage_path,
    document_acquisition_policy,
)
from collector.infra.acquisition.ssrf import UrlSafetyPolicy
from collector.infra.acquisition.storage import LocalArtifactStorage

__all__ = [
    "HttpxBinaryDownloader",
    "LocalArtifactStorage",
    "UrlSafetyPolicy",
    "artifact_storage_path",
    "document_acquisition_policy",
]
