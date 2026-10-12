"""Motor determinístico de triagem. Precedência centralizada. Sem IA."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
    ReasonCode.EXCLUDED_CONTEXT: (
        "O contexto encontrado é explicitamente externo ao escopo de climatização predial."
    ),
    ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT: (
        "Há sinais relacionados ao perfil, mas o serviço não é suficientemente "
        "claro para decisão segura."
    ),
    ReasonCode.NO_RELEVANT_SCOPE: (
        "O perfil foi aplicado e não encontrou evidência de aderência."
    ),
    ReasonCode.EMPTY_DESCRIPTION: ("A observação não possui descrição para avaliar."),
}

_CLAUSE_SEPARATOR = re.compile(r"[.;:\n]+")
_ASSOCIATION_FILLERS = frozenset(
    {
        "a",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "linear",
        "lineares",
        "metro",
        "metros",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "para",
        "por",
    }
)


@dataclass(frozen=True)
class _Match:
    category: str
    configured_term: str
    start: int
    end: int


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
            evidence = (
                _collect_evidence(tokenize(description), profile)
                if profile.association_window_tokens is None
                else _collect_contextual_evidence(description, profile)
            )
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
    has_ambiguous_context = "ambiguous_context" in categories
    has_excluded_context = "excluded_context" in categories
    has_maintenance = "maintenance" in categories
    has_sanitization = "sanitization" in categories
    has_service = has_maintenance or has_sanitization
    has_installation = "installation" in categories
    has_purchase = "purchase" in categories
    has_parts = "parts" in categories
    relevant = has_context and has_service

    if has_excluded_context:
        return ScreeningStatus.DISCARDED, ReasonCode.EXCLUDED_CONTEXT
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
    if has_ambiguous_context:
        return ScreeningStatus.PENDING, ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT
    if has_service and (has_installation or has_purchase or has_parts):
        return ScreeningStatus.PENDING, ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT
    return ScreeningStatus.DISCARDED, ReasonCode.NO_RELEVANT_SCOPE


def _collect_evidence(
    tokens: tuple[str, ...], profile: ScreeningProfile
) -> tuple[ScreeningEvidence, ...]:
    return tuple(
        _to_evidence(item, tokens) for item in _collect_matches(tokens, profile)
    )


def _collect_contextual_evidence(
    description: str, profile: ScreeningProfile
) -> tuple[ScreeningEvidence, ...]:
    window = profile.association_window_tokens
    if window is None:
        raise ValueError("perfil contextual exige association_window_tokens")
    evidence: list[ScreeningEvidence] = []
    for clause in _CLAUSE_SEPARATOR.split(description):
        tokens = tokenize(clause)
        matches = _collect_matches(tokens, profile)
        contexts = tuple(
            item
            for item in matches
            if item.category in {"context", "ambiguous_context"}
        )
        associated = {
            item
            for item in matches
            if item.category in {"context", "ambiguous_context"}
            or any(_token_gap(item, context, tokens) <= window for context in contexts)
        }
        exclusions = tuple(
            item
            for item in matches
            if item.category in {"installation", "purchase", "parts"}
        )
        services = tuple(
            item for item in matches if item.category in {"maintenance", "sanitization"}
        )
        associated_exclusions = tuple(item for item in exclusions if item in associated)
        associated.update(
            service
            for service in services
            if any(
                _token_gap(service, exclusion, tokens) == 0
                for exclusion in associated_exclusions
            )
        )
        if any(service in associated for service in services) and contexts:
            associated.update(exclusions)
        for item in matches:
            if item in associated:
                evidence.append(_to_evidence(item, tokens))
    return tuple(evidence)


def _collect_matches(
    tokens: tuple[str, ...], profile: ScreeningProfile
) -> tuple[_Match, ...]:
    buckets = (
        ("context", profile.context_terms),
        ("ambiguous_context", profile.ambiguous_context_terms),
        ("excluded_context", profile.excluded_context_terms),
        ("maintenance", profile.maintenance_terms),
        ("sanitization", profile.sanitization_terms),
        ("installation", profile.installation_terms),
        ("purchase", profile.purchase_terms),
        ("parts", profile.parts_terms),
    )
    matches: list[_Match] = []
    for category, terms in buckets:
        for term in terms:
            for start, end in find_matches(tokens, term):
                matches.append(
                    _Match(
                        category=category,
                        configured_term=term,
                        start=start,
                        end=end,
                    )
                )
    return tuple(matches)


def _to_evidence(item: _Match, tokens: tuple[str, ...]) -> ScreeningEvidence:
    return ScreeningEvidence(
        category=item.category,
        configured_term=item.configured_term,
        field=ANALYZED_FIELD,
        matched_text=matched_span(tokens, item.start, item.end),
    )


def _token_gap(left: _Match, right: _Match, tokens: tuple[str, ...]) -> int:
    if left.end <= right.start:
        between = tokens[left.end : right.start]
    elif right.end <= left.start:
        between = tokens[right.end : left.start]
    else:
        between = ()
    return sum(
        token not in _ASSOCIATION_FILLERS and not token.isdecimal() for token in between
    )


def _reason_text(reason: ReasonCode, evidence: Sequence[ScreeningEvidence]) -> str:
    base = _REASON_TEXT[reason]
    if not evidence:
        return base
    terms = ", ".join(sorted({item.configured_term for item in evidence}))
    return f"{base} Termos: {terms}."
