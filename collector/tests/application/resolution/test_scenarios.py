"""Casos manuais controlados: 3341, recuperação, descarte, incompleto."""

from collector.application.document_screening.compare import DivergenceKind, compare_screenings
from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.domain import ScreeningStatus
from tests.application.resolution.helpers import (
    document_case,
    known_3341_document,
    known_3341_initial,
    resolve,
)
from tests.application.screening.helpers import screen


def test_known_3341_fixture_is_pending_inconclusive() -> None:
    initial = known_3341_initial()
    document = known_3341_document(initial.process_id)
    assert initial.state is ScreeningStatus.PENDING
    assert initial.reason_code.value == "MIXED_MAINTENANCE_SUPPLY"
    assert document.state is ScreeningStatus.PENDING
    assert document.reason_code.value == "DOCUMENT_NO_DECISIVE_EVIDENCE"
    assert document.coverage.complete is True
    result = resolve(initial, document)
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is OperationalReasonCode.DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE
    assert result.rule_code is OperationalRuleCode.R_DOC_NON_DECISIVE
    assert result.state_diverged is False
    assert result.reason_diverged is True
    assert result.divergence_kind is DivergenceKind.REASON_ONLY
    comparison = compare_screenings(initial, document)
    assert comparison.state_diverged is False
    assert comparison.reason_diverged is True


def test_recovery_from_initial_discard() -> None:
    result = resolve(
        screen("Aquisição de condicionadores de ar."),
        document_case("Contratação de manutenção preventiva dos aparelhos de ar condicionado."),
    )
    assert result.initial_state is ScreeningStatus.DISCARDED
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is OperationalReasonCode.DOCUMENT_CONFIRMED_RELEVANCE
    assert result.rule_code is OperationalRuleCode.R_DOC_POSITIVE_COMPLETE


def test_confirmed_discard_of_initial_candidate() -> None:
    result = resolve(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        document_case("Aquisição de condicionadores de ar."),
    )
    assert result.initial_state is ScreeningStatus.CANDIDATE
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_PURCHASE
    assert result.rule_code is OperationalRuleCode.R_DOC_NEGATIVE_COMPLETE


def test_negative_incomplete_stays_pending() -> None:
    result = resolve(
        screen("Manutenção preventiva de aparelhos de ar condicionado."),
        document_case("Serviço de instalação de aparelhos de ar condicionado.", complete=False),
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.coverage_complete is False
    assert result.rule_code is OperationalRuleCode.R_DOC_NEGATIVE_INCOMPLETE


def test_initial_only_discard_is_not_document_confirmed() -> None:
    result = resolve(screen("Aquisição de condicionadores de ar."), None)
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is OperationalReasonCode.INITIAL_SCREENING_ONLY
    assert result.document_evaluation_id is None
