"""Métricas da resolução. Independentes de CollectionRound."""

from __future__ import annotations

from collections.abc import Sequence

from collector.application.resolution.reasons import OperationalRuleCode
from collector.application.resolution.results import OperationalResolution, OperationalSummary
from collector.domain import ScreeningStatus


def summarize_resolutions(
    resolutions: Sequence[OperationalResolution],
) -> OperationalSummary:
    candidate = pending = discarded = 0
    initial_only = document_based = incomplete = 0
    state_div = reason_div = 0
    recovered = downgraded = changed = unchanged = 0
    for resolution in resolutions:
        if resolution.state is ScreeningStatus.CANDIDATE:
            candidate += 1
        elif resolution.state is ScreeningStatus.PENDING:
            pending += 1
        elif resolution.state is ScreeningStatus.DISCARDED:
            discarded += 1
        if resolution.rule_code is OperationalRuleCode.R_INITIAL_ONLY:
            initial_only += 1
        else:
            document_based += 1
        if resolution.document_evaluation_id is not None and not resolution.coverage_complete:
            incomplete += 1
        if resolution.state_diverged:
            state_div += 1
        if resolution.reason_diverged:
            reason_div += 1
        if resolution.initial_state is resolution.state:
            unchanged += 1
        else:
            changed += 1
        if (
            resolution.initial_state is ScreeningStatus.DISCARDED
            and resolution.state in {ScreeningStatus.CANDIDATE, ScreeningStatus.PENDING}
            and resolution.document_evaluation_id is not None
        ):
            recovered += 1
        if (
            resolution.initial_state is ScreeningStatus.CANDIDATE
            and resolution.state is ScreeningStatus.DISCARDED
        ):
            downgraded += 1
    return OperationalSummary(
        resolutions_total=len(resolutions),
        candidate=candidate,
        pending=pending,
        discarded=discarded,
        initial_only=initial_only,
        document_based=document_based,
        incomplete_document=incomplete,
        state_divergences=state_div,
        reason_divergences=reason_div,
        recovered_from_initial_discard=recovered,
        candidate_downgraded_to_discarded=downgraded,
        changed_state=changed,
        unchanged_state=unchanged,
    )
