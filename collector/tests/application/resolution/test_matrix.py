"""Matriz completa Initial × Document × cobertura."""

import pytest

from collector.application.resolution.reasons import (
    OperationalReasonCode,
    OperationalRuleCode,
)
from collector.domain import ScreeningStatus
from tests.application.resolution.helpers import document_case, resolve
from tests.application.screening.helpers import screen

INITIAL = {
    "CANDIDATE": "Manutenção preventiva de aparelhos de ar condicionado.",
    "PENDING": "Manutenção e fornecimento de aparelhos de ar condicionado.",
    "DISCARDED": "Aquisição de condicionadores de ar.",
}
DOCUMENT = {
    "positive": "Contratação de manutenção preventiva dos aparelhos de ar condicionado.",
    "mixed": "Prestação de serviços de manutenção preventiva e fornecimento de peças para sistemas de climatização.",
    "negative": "Serviço de instalação de aparelhos de ar condicionado.",
    "non_decisive": "Regras para apresentação da proposta.",
}


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
def test_initial_only_preserves_state(initial_key: str) -> None:
    result = resolve(screen(INITIAL[initial_key]), None)
    assert result.state is ScreeningStatus[initial_key]
    assert result.reason_code is OperationalReasonCode.INITIAL_SCREENING_ONLY
    assert result.rule_code is OperationalRuleCode.R_INITIAL_ONLY
    assert result.coverage_complete is False
    assert result.document_evaluation_id is None
    assert result.state_diverged is None


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
@pytest.mark.parametrize("complete", [True, False])
def test_positive_document_is_candidate(initial_key: str, complete: bool) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["positive"], complete=complete))
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is OperationalReasonCode.DOCUMENT_CONFIRMED_RELEVANCE
    assert result.rule_code is (
        OperationalRuleCode.R_DOC_POSITIVE_COMPLETE
        if complete
        else OperationalRuleCode.R_DOC_POSITIVE_INCOMPLETE
    )
    assert result.coverage_complete is complete


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
@pytest.mark.parametrize("complete", [True, False])
def test_mixed_document_is_pending(initial_key: str, complete: bool) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["mixed"], complete=complete))
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is OperationalReasonCode.DOCUMENT_MIXED_SCOPE_REQUIRES_REVIEW
    assert result.rule_code is OperationalRuleCode.R_DOC_MIXED


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
def test_negative_complete_is_discarded(initial_key: str) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["negative"], complete=True))
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is OperationalReasonCode.DOCUMENT_CONFIRMED_ISOLATED_INSTALLATION
    assert result.rule_code is OperationalRuleCode.R_DOC_NEGATIVE_COMPLETE


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
def test_negative_incomplete_is_pending(initial_key: str) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["negative"], complete=False))
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is OperationalReasonCode.DOCUMENT_INCOMPLETE_REVIEW_REQUIRED
    assert result.rule_code is OperationalRuleCode.R_DOC_NEGATIVE_INCOMPLETE


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
def test_non_decisive_complete_is_pending(initial_key: str) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["non_decisive"], complete=True))
    assert result.state is ScreeningStatus.PENDING
    assert result.rule_code is OperationalRuleCode.R_DOC_NON_DECISIVE
    if initial_key == "DISCARDED":
        assert result.reason_code is OperationalReasonCode.DOCUMENT_INCONCLUSIVE
    else:
        assert result.reason_code is OperationalReasonCode.DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE


@pytest.mark.parametrize("initial_key", ["CANDIDATE", "PENDING", "DISCARDED"])
def test_non_decisive_incomplete_is_pending(initial_key: str) -> None:
    result = resolve(screen(INITIAL[initial_key]), document_case(DOCUMENT["non_decisive"], complete=False))
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is OperationalReasonCode.DOCUMENT_INCOMPLETE_REVIEW_REQUIRED
    assert result.rule_code is OperationalRuleCode.R_DOC_INCOMPLETE
