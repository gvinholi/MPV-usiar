from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from collector.application.screening import ReasonCode, usiar_v1, usiar_v2
from collector.domain import ScreeningStatus
from tests.application.screening.helpers import screen


CORPUS_PATH = Path(__file__).with_name("usiar_v2_corpus.json")
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case["case_id"])
def test_versioned_corpus(case) -> None:
    result = screen(case["description"], usiar_v2())
    assert result.state.value == case["expected_v2"]
    if case["kind"] == "real":
        assert case["official_id"]
        assert case["source_url"].startswith("https://pncp.gov.br/")
    else:
        assert case["official_id"] is None
        assert case["source_url"] is None


def test_context_distance_prevents_cross_scope_candidate() -> None:
    result = screen(
        "Manutenção predial e aquisição de aparelhos de ar-condicionado",
        usiar_v2(),
    )
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.ISOLATED_EQUIPMENT_PURCHASE
    assert "maintenance" not in {item.category for item in result.evidence}


def test_clauses_do_not_combine_independent_terms() -> None:
    result = screen(
        "Manutenção do telhado. Aquisição de aparelhos de ar condicionado.",
        usiar_v2(),
    )
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.ISOLATED_EQUIPMENT_PURCHASE


def test_vehicle_air_conditioning_is_explicitly_out_of_scope() -> None:
    result = screen("Manutenção de ar-condicionado veicular.", usiar_v2())
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.EXCLUDED_CONTEXT
    assert any(item.category == "excluded_context" for item in result.evidence)


def test_v1_configuration_and_semantics_remain_legacy() -> None:
    profile = usiar_v1()
    assert set(profile.configuration()) == {
        "context_terms",
        "maintenance_terms",
        "sanitization_terms",
        "installation_terms",
        "purchase_terms",
        "parts_terms",
    }
    legacy_false_positive = screen(
        "Manutenção predial e aquisição de aparelhos de ar-condicionado", profile
    )
    assert legacy_false_positive.state is ScreeningStatus.PENDING
    assert legacy_false_positive.reason_code is ReasonCode.MIXED_MAINTENANCE_SUPPLY


def test_v1_and_v2_have_stable_distinct_identities() -> None:
    v1 = usiar_v1()
    v2 = usiar_v2()
    assert v1.identity == "USIAR/v1"
    assert v2.identity == "USIAR/v2"
    assert v1.id != v2.id
    assert v2.association_window_tokens == 1


def test_real_corpus_comparison_is_reproducible() -> None:
    real = [case for case in CORPUS if case["kind"] == "real"]
    v1 = Counter(screen(case["description"], usiar_v1()).state.value for case in real)
    v2 = Counter(screen(case["description"], usiar_v2()).state.value for case in real)
    assert sum(v1.values()) == sum(v2.values()) == 9
    assert v1 == {"CANDIDATE": 3, "PENDING": 3, "DISCARDED": 3}
    assert v2 == {"CANDIDATE": 2, "PENDING": 3, "DISCARDED": 4}
