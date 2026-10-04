"""Motor determinístico de triagem. Precedência centralizada. Sem IA."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.screening.matching import find_matches, matched_span
from collector.application.screening.normalize import tokenize
from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.reasons import ReasonCode
from collector.application.screening.results import (
    ENGINE_VERSION,
    ScreeningEvaluation,
    ScreeningEvidence,
)
from collector.domain import ScreeningStatus
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]
ANALYZED_FIELD = "description"

_REASON_TEXT = {
    ReasonCode.RELEVANT_MAINTENANCE: (
        "Há evidência de manutenção relevante em contexto de climatização."
    ),
    ReasonCode.RELEVANT_SANITIZATION: (
        "Há evidência de higienização relevante em contexto de climatização."
    ),
    ReasonCode.MIXED_MAINTENANCE_INSTALLATION: (
        "Há manutenção ou higienização relevante junto de instalação; "
        "escopo misto exige avaliação humana."
    ),
    ReasonCode.MIXED_MAINTENANCE_SUPPLY: (
        "Há manutenção ou higienização relevante junto de aquisição ou peças; "
        "escopo misto exige avaliação humana."
    ),
    ReasonCode.ISOLATED_INSTALLATION: (
        "O objeto é instalação em contexto de climatização, sem manutenção "
        "ou higienização relevante."
    ),
    ReasonCode.ISOLATED_EQUIPMENT_PURCHASE: (
        "O objeto é aquisição ou fornecimento de equipamento de climatização, "
        "sem manutenção ou higienização relevante."
    ),
    ReasonCode.ISOLATED_PARTS_SUPPLY: (
        "O objeto é fornecimento de peças ou componentes de climatização, "
        "sem manutenção ou higienização relevante."
    ),
    ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT: (
        "Há sinais relacionados ao perfil, mas o serviço não é suficientemente "
        "claro para decisão segura."
    ),
    ReasonCode.NO_RELEVANT_SCOPE: (
        "O perfil foi aplicado e não encontrou evidência de aderência."
    ),
    ReasonCode.EMPTY_DESCRIPTION: (
        "A observação não possui descrição para avaliar."
    ),
}


class ScreeningEngine:
    version = ENGINE_VERSION

    def __init__(self, *, clock: Clock = utc_now, new_id: IdFactory = uuid4) -> None:
        self._clock = clock
        self._new_id = new_id

    def evaluate(
        self,
        profile: ScreeningProfile,
        *,
        description: str | None,
        process_id: UUID,
        observation_id: UUID,
        profile_id: UUID | None = None,
    ) -> ScreeningEvaluation:
        if description is None or not description.strip():
            state = ScreeningStatus.PENDING
            reason = ReasonCode.EMPTY_DESCRIPTION
            evidence: tuple[ScreeningEvidence, ...] = ()
        else:
            tokens = tokenize(description)
            evidence = _collect_evidence(tokens, profile)
            state, reason = decide(evidence)
        return ScreeningEvaluation(
            id=self._new_id(),
            process_id=process_id,
            observation_id=observation_id,
            profile_code=profile.code,
            profile_version=profile.version,
            profile_id=profile_id or profile.id,
            state=state,
            reason_code=reason,
            reason_text=_reason_text(reason, evidence),
            evaluated_at=self._clock(),
            engine_version=self.version,
            field=ANALYZED_FIELD,
            evidence=evidence,
        )


def decide(evidence: Sequence[ScreeningEvidence]) -> tuple[ScreeningStatus, ReasonCode]:
    """Precedência única da triagem automática."""

    categories = {item.category for item in evidence}
    has_context = "context" in categories
    has_maintenance = "maintenance" in categories
    has_sanitization = "sanitization" in categories
    has_service = has_maintenance or has_sanitization
    has_installation = "installation" in categories
    has_purchase = "purchase" in categories
    has_parts = "parts" in categories
    relevant = has_context and has_service

    if relevant and has_installation:
        return ScreeningStatus.PENDING, ReasonCode.MIXED_MAINTENANCE_INSTALLATION
    if relevant and (has_purchase or has_parts):
        return ScreeningStatus.PENDING, ReasonCode.MIXED_MAINTENANCE_SUPPLY
    if relevant and has_maintenance:
        return ScreeningStatus.CANDIDATE, ReasonCode.RELEVANT_MAINTENANCE
    if relevant and has_sanitization:
        return ScreeningStatus.CANDIDATE, ReasonCode.RELEVANT_SANITIZATION
    if has_context and has_installation:
        return ScreeningStatus.DISCARDED, ReasonCode.ISOLATED_INSTALLATION
    if has_context and has_parts:
        return ScreeningStatus.DISCARDED, ReasonCode.ISOLATED_PARTS_SUPPLY
    if has_context and has_purchase:
        return ScreeningStatus.DISCARDED, ReasonCode.ISOLATED_EQUIPMENT_PURCHASE
    if has_context:
        return ScreeningStatus.PENDING, ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT
    if has_service and (has_installation or has_purchase or has_parts):
        return ScreeningStatus.PENDING, ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT
    return ScreeningStatus.DISCARDED, ReasonCode.NO_RELEVANT_SCOPE


def _collect_evidence(
    tokens: tuple[str, ...], profile: ScreeningProfile
) -> tuple[ScreeningEvidence, ...]:
    buckets = (
        ("context", profile.context_terms),
        ("maintenance", profile.maintenance_terms),
        ("sanitization", profile.sanitization_terms),
        ("installation", profile.installation_terms),
        ("purchase", profile.purchase_terms),
        ("parts", profile.parts_terms),
    )
    evidence: list[ScreeningEvidence] = []
    for category, terms in buckets:
        for term in terms:
            for start, end in find_matches(tokens, term):
                evidence.append(
                    ScreeningEvidence(
                        category=category,
                        configured_term=term,
                        field=ANALYZED_FIELD,
                        matched_text=matched_span(tokens, start, end),
                    )
                )
    return tuple(evidence)


def _reason_text(reason: ReasonCode, evidence: Sequence[ScreeningEvidence]) -> str:
    base = _REASON_TEXT[reason]
    if not evidence:
        return base
    terms = ", ".join(sorted({item.configured_term for item in evidence}))
    return f"{base} Termos: {terms}."
