"""Aquisição controlada de artefatos. Sem extração textual e sem triagem."""

from collector.application.acquisition.acquire import AcquireDocumentArtifact
from collector.application.acquisition.errors import AcquisitionError
from collector.application.acquisition.filetype import detect_file_type
from collector.application.acquisition.persist import (
    PersistAcquisitionOutcome,
    PersistDocumentAcquisition,
)
from collector.application.acquisition.policy import (
    DEFAULT_MAX_DOWNLOAD_BYTES,
    DocumentAcquisitionPolicy,
)
from collector.application.acquisition.ports import (
    ArtifactStorage,
    BinaryDownloader,
    DocumentAcquisitionRepository,
)
from collector.application.acquisition.reasons import AcquisitionReason
from collector.application.acquisition.results import (
    AcquisitionIssue,
    ArchiveSummary,
    DocumentAcquisitionResult,
)
from collector.application.acquisition.zipinspect import classify_archive_path, inspect_zip

__all__ = [
    "DEFAULT_MAX_DOWNLOAD_BYTES",
    "AcquireDocumentArtifact",
    "AcquisitionError",
    "AcquisitionIssue",
    "AcquisitionReason",
    "ArchiveSummary",
    "ArtifactStorage",
    "BinaryDownloader",
    "DocumentAcquisitionPolicy",
    "DocumentAcquisitionRepository",
    "DocumentAcquisitionResult",
    "PersistAcquisitionOutcome",
    "PersistDocumentAcquisition",
    "classify_archive_path",
    "detect_file_type",
    "inspect_zip",
]
