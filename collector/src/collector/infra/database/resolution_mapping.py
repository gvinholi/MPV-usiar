"""Tradução entre resolução operacional e linha persistida."""

from __future__ import annotations

from collector.application.document_screening.compare import DivergenceKind
from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.application.resolution.results import OperationalResolution
from collector.domain import ScreeningStatus


def resolution_from_row(row) -> OperationalResolution:
    if row.state_diverged is None and row.reason_diverged is None:
        kind = None
    elif row.state_diverged and row.reason_diverged:
        kind = DivergenceKind.STATE_AND_REASON
    elif row.state_diverged:
        kind = DivergenceKind.STATE_ONLY
    elif row.reason_diverged:
        kind = DivergenceKind.REASON_ONLY
    else:
        kind = DivergenceKind.NONE
    return OperationalResolution(
        id=row.id,
        process_id=row.process_id,
        profile_id=row.profile_id,
        profile_code=row.profile.code,
        profile_version=row.profile.version,
        initial_evaluation_id=row.initial_evaluation_id,
        document_evaluation_id=row.document_evaluation_id,
        resolver_engine_version=row.resolver_engine_version,
        resolution_fingerprint=row.resolution_fingerprint,
        state=ScreeningStatus(row.state),
        reason_code=OperationalReasonCode(row.reason_code),
        reason_text=row.reason_text,
        rule_code=OperationalRuleCode(row.rule_code),
        coverage_complete=row.coverage_complete,
        state_diverged=row.state_diverged,
        reason_diverged=row.reason_diverged,
        divergence_kind=kind,
        resolved_at=row.resolved_at,
        initial_state=ScreeningStatus(row.initial_state),
        document_state=(
            None if row.document_state is None else ScreeningStatus(row.document_state)
        ),
    )
