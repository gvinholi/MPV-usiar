"""Triagem determinística por perfil configurável."""

from collector.application.screening.engine import ScreeningEngine, decide
from collector.application.screening.errors import (
    IncompatibleProfileError,
    ScreeningError,
)
from collector.application.screening.persist import (
    PersistScreening,
    PersistScreeningOutcome,
)
from collector.application.screening.ports import ScreeningRepository
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.profiles import (
    USIAR_V1_ID,
    USIAR_V2_ID,
    usiar_v1,
    usiar_v2,
)
from collector.application.screening.reasons import ReasonCode
from collector.application.screening.results import (
    ENGINE_VERSION,
    ScreeningEvaluation,
    ScreeningEvidence,
    ScreeningSummary,
    summarize,
)

__all__ = [
    "ENGINE_VERSION",
    "IncompatibleProfileError",
    "PersistScreening",
    "PersistScreeningOutcome",
    "ReasonCode",
    "ScreeningEngine",
    "ScreeningError",
    "ScreeningEvaluation",
    "ScreeningEvidence",
    "ScreeningProfile",
    "ScreeningRepository",
    "ScreeningSummary",
    "USIAR_V1_ID",
    "USIAR_V2_ID",
    "decide",
    "summarize",
    "usiar_v1",
    "usiar_v2",
]
