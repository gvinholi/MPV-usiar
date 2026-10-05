"""Resolução operacional determinística. Terceira camada."""

from collector.application.resolution.errors import (
    InitialScreeningRequiredError,
    ProcessMismatchError,
    ProfileMismatchError,
    ResolutionError,
)
from collector.application.resolution.fingerprint import (
    RESOLVER_ENGINE_VERSION,
    initial_input_fingerprint,
    resolution_fingerprint,
)
from collector.application.resolution.persist import (
    PersistOperationalResolution,
    PersistResolutionOutcome,
)
from collector.application.resolution.ports import OperationalResolutionRepository
from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.application.resolution.resolver import OperationalResolver
from collector.application.resolution.results import OperationalResolution, OperationalSummary
from collector.application.resolution.strength import DocumentStrength, document_strength
from collector.application.resolution.summarize import summarize_resolutions

__all__ = [
    "RESOLVER_ENGINE_VERSION",
    "DocumentStrength",
    "InitialScreeningRequiredError",
    "OperationalReasonCode",
    "OperationalResolution",
    "OperationalResolutionRepository",
    "OperationalResolver",
    "OperationalRuleCode",
    "OperationalSummary",
    "PersistOperationalResolution",
    "PersistResolutionOutcome",
    "ProcessMismatchError",
    "ProfileMismatchError",
    "ResolutionError",
    "document_strength",
    "initial_input_fingerprint",
    "resolution_fingerprint",
    "summarize_resolutions",
]
