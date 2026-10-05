"""Resolver operacional puro. Sem I/O e sem pesos."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.document_screening.compare import compare_screenings
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.resolution.errors import (
    InitialScreeningRequiredError,
    ProcessMismatchError,
    ProfileMismatchError,
)
from collector.application.resolution.fingerprint import (
    RESOLVER_ENGINE_VERSION,
    initial_input_fingerprint,
    resolution_fingerprint,
)
from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.application.resolution.results import OperationalResolution
from collector.application.resolution.strength import DocumentStrength, document_strength
from collector.application.screening.results import ScreeningEvaluation
from collector.domain import ScreeningStatus
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]

_NEGATIVE_REASON = {
    DocumentReasonCode.DOCUMENT_ISOLATED_INSTALLATION: (
        OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_INSTALLATION
    ),
    DocumentReasonCode.DOCUMENT_ISOLATED_EQUIPMENT_PURCHASE: (
        OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_PURCHASE
    ),
    DocumentReasonCode.DOCUMENT_ISOLATED_PARTS_SUPPLY: (
        OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_PARTS
    ),
}

_REASON_TEXT = {
    OperationalReasonCode.INITIAL_SCREENING_ONLY: (
        "Ainda não há triagem documental. O estado operacional replica a "
        "triagem da description PNCP."
    ),
    OperationalReasonCode.DOCUMENT_CONFIRMED_RELEVANCE: (
        "Os documentos confirmam manutenção relevante em contexto de climatização."
    ),
    OperationalReasonCode.DOCUMENT_CONFIRMED_SANITIZATION: (
        "Os documentos confirmam higienização relevante em contexto de climatização."
    ),
    OperationalReasonCode.DOCUMENT_MIXED_SCOPE_REQUIRES_REVIEW: (
        "Os documentos mostram escopo relevante misto; revisão humana é necessária."
    ),
    OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_INSTALLATION: (
        "Os documentos, com cobertura completa, confirmam instalação isolada."
    ),
    OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_PURCHASE: (
        "Os documentos, com cobertura completa, confirmam aquisição isolada."
    ),
    OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_PARTS: (
        "Os documentos, com cobertura completa, confirmam fornecimento isolado de peças."
    ),
    OperationalReasonCode.DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE: (
        "Os documentos foram analisados e não confirmaram a relevância sugerida "
        "pela description PNCP. Ausência de termo extraído não prova irrelevância."
    ),
    OperationalReasonCode.DOCUMENT_INCONCLUSIVE: (
        "A triagem documental não é decisiva. O estado permanece pendente "
        "para não perder oportunidade nem afirmar irrelevância."
    ),
    OperationalReasonCode.DOCUMENT_INCOMPLETE_REVIEW_REQUIRED: (
        "A cobertura documental está incompleta. Não há descarte automático."
    ),
}


class OperationalResolver:
    version = RESOLVER_ENGINE_VERSION

    def __init__(self, *, clock: Clock = utc_now, new_id: IdFactory = uuid4) -> None:
        self._clock = clock
        self._new_id = new_id

    def resolve(
        self,
        initial: ScreeningEvaluation | None,
        document: DocumentScreeningEvaluation | None,
    ) -> OperationalResolution:
        if initial is None:
            raise InitialScreeningRequiredError("INITIAL_SCREENING_REQUIRED")
        if document is not None:
            if document.process_id != initial.process_id:
                raise ProcessMismatchError("avaliações de processos diferentes")
            if (
                document.profile_code != initial.profile_code
                or document.profile_version != initial.profile_version
            ):
                raise ProfileMismatchError("avaliações de perfis incompatíveis")

        state, reason, rule, coverage_complete = _apply_matrix(initial, document)
        comparison = (
            None
            if document is None
            else compare_screenings(initial, document)
        )
        return OperationalResolution(
            id=self._new_id(),
            process_id=initial.process_id,
            profile_code=initial.profile_code,
            profile_version=initial.profile_version,
            profile_id=initial.profile_id,
            initial_evaluation_id=initial.id,
            document_evaluation_id=None if document is None else document.id,
            resolver_engine_version=self.version,
            resolution_fingerprint=resolution_fingerprint(
                initial, document, resolver_version=self.version
            ),
            state=state,
            reason_code=reason,
            reason_text=_REASON_TEXT[reason],
            rule_code=rule,
            coverage_complete=coverage_complete,
            state_diverged=None if comparison is None else comparison.state_diverged,
            reason_diverged=None if comparison is None else comparison.reason_diverged,
            divergence_kind=None if comparison is None else comparison.divergence_kind,
            resolved_at=self._clock(),
            initial_state=initial.state,
            document_state=None if document is None else document.state,
            document_set_fingerprint=(
                None if document is None else document.document_set_fingerprint
            ),
            initial_input_fingerprint=initial_input_fingerprint(initial),
        )


def _apply_matrix(
    initial: ScreeningEvaluation,
    document: DocumentScreeningEvaluation | None,
) -> tuple[ScreeningStatus, OperationalReasonCode, OperationalRuleCode, bool]:
    if document is None:
        return (
            initial.state,
            OperationalReasonCode.INITIAL_SCREENING_ONLY,
            OperationalRuleCode.R_INITIAL_ONLY,
            False,
        )

    strength = document_strength(document.reason_code)
    complete = document.coverage.complete
    has_exclusion_evidence = any(
        item.category in {"installation", "purchase", "parts"} and not item.negated
        for item in document.evidence
    )

    if strength is DocumentStrength.POSITIVE_DECISIVE:
        reason = (
            OperationalReasonCode.DOCUMENT_CONFIRMED_SANITIZATION
            if document.reason_code is DocumentReasonCode.DOCUMENT_RELEVANT_SANITIZATION
            else OperationalReasonCode.DOCUMENT_CONFIRMED_RELEVANCE
        )
        rule = (
            OperationalRuleCode.R_DOC_POSITIVE_COMPLETE
            if complete
            else OperationalRuleCode.R_DOC_POSITIVE_INCOMPLETE
        )
        return ScreeningStatus.CANDIDATE, reason, rule, complete

    if strength is DocumentStrength.MIXED_DECISIVE:
        return (
            ScreeningStatus.PENDING,
            OperationalReasonCode.DOCUMENT_MIXED_SCOPE_REQUIRES_REVIEW,
            OperationalRuleCode.R_DOC_MIXED,
            complete,
        )

    if strength is DocumentStrength.NEGATIVE_DECISIVE:
        if complete and has_exclusion_evidence:
            return (
                ScreeningStatus.DISCARDED,
                _NEGATIVE_REASON[document.reason_code],
                OperationalRuleCode.R_DOC_NEGATIVE_COMPLETE,
                True,
            )
        return (
            ScreeningStatus.PENDING,
            OperationalReasonCode.DOCUMENT_INCOMPLETE_REVIEW_REQUIRED,
            OperationalRuleCode.R_DOC_NEGATIVE_INCOMPLETE,
            complete,
        )

    if not complete:
        return (
            ScreeningStatus.PENDING,
            OperationalReasonCode.DOCUMENT_INCOMPLETE_REVIEW_REQUIRED,
            OperationalRuleCode.R_DOC_INCOMPLETE,
            False,
        )
    if initial.state is ScreeningStatus.CANDIDATE:
        reason = OperationalReasonCode.DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE
    elif initial.state is ScreeningStatus.PENDING:
        reason = OperationalReasonCode.DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE
    else:
        reason = OperationalReasonCode.DOCUMENT_INCONCLUSIVE
    return (
        ScreeningStatus.PENDING,
        reason,
        OperationalRuleCode.R_DOC_NON_DECISIVE,
        True,
    )
