"""Tradução entre avaliação de aplicação e linhas de persistência."""

from __future__ import annotations

from collector.application.screening.profile import ScreeningProfile
from collector.application.screening.reasons import ReasonCode
from collector.application.screening.results import (
    ScreeningEvaluation,
    ScreeningEvidence,
)
from collector.domain import ScreeningStatus


def profile_configuration_payload(profile: ScreeningProfile) -> dict[str, object]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in profile.configuration().items()
    }


def profile_from_payload(
    *,
    id,
    code: str,
    name: str,
    version: str,
    active: bool,
    configuration: dict[str, object],
) -> ScreeningProfile:
    return ScreeningProfile(
        id=id,
        code=code,
        name=name,
        version=version,
        active=active,
        context_terms=tuple(configuration.get("context_terms", ())),
        maintenance_terms=tuple(configuration.get("maintenance_terms", ())),
        sanitization_terms=tuple(configuration.get("sanitization_terms", ())),
        installation_terms=tuple(configuration.get("installation_terms", ())),
        purchase_terms=tuple(configuration.get("purchase_terms", ())),
        parts_terms=tuple(configuration.get("parts_terms", ())),
        ambiguous_context_terms=tuple(configuration.get("ambiguous_context_terms", ())),
        excluded_context_terms=tuple(configuration.get("excluded_context_terms", ())),
        association_window_tokens=configuration.get("association_window_tokens"),
    )


def evaluation_from_row(
    *,
    id,
    process_id,
    observation_id,
    profile_id,
    profile_code: str,
    profile_version: str,
    state: str,
    reason_code: str,
    reason_text: str,
    evaluated_at,
    engine_version: str,
    evidence_rows: list,
) -> ScreeningEvaluation:
    evidence = tuple(
        ScreeningEvidence(
            category=row.category,
            configured_term=row.configured_term,
            field=row.field,
            matched_text=row.matched_text,
        )
        for row in evidence_rows
    )
    return ScreeningEvaluation(
        id=id,
        process_id=process_id,
        observation_id=observation_id,
        profile_id=profile_id,
        profile_code=profile_code,
        profile_version=profile_version,
        state=ScreeningStatus(state),
        reason_code=ReasonCode(reason_code),
        reason_text=reason_text,
        evaluated_at=evaluated_at,
        engine_version=engine_version,
        field="description",
        evidence=evidence,
    )
