"""Motor USIAR: positivos, mistos, exclusões, falsos positivos e precedência."""

from decimal import Decimal
from uuid import uuid4

from collector.application.screening import (
    ReasonCode,
    ScreeningEngine,
    ScreeningProfile,
    usiar_v1,
)
from collector.domain import ScreeningStatus
from tests.application.screening.helpers import screen


def test_candidate_maintenance_preventive_corrective() -> None:
    result = screen(
        "Contratação de empresa especializada para manutenção preventiva e "
        "corretiva de aparelhos de ar condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is ReasonCode.RELEVANT_MAINTENANCE
    assert result.state not in {ScreeningStatus.SELECTED, ScreeningStatus.CONFIRMED}


def test_candidate_continued_climatization() -> None:
    result = screen(
        "Serviços continuados de manutenção preventiva dos sistemas de climatização."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is ReasonCode.RELEVANT_MAINTENANCE


def test_candidate_sanitization() -> None:
    result = screen(
        "Contratação de serviços de higienização e limpeza de aparelhos de ar-condicionado."
    )
    assert result.state is ScreeningStatus.CANDIDATE
    assert result.reason_code is ReasonCode.RELEVANT_SANITIZATION


def test_candidate_vrf() -> None:
    result = screen("Manutenção corretiva em sistema VRF.")
    assert result.state is ScreeningStatus.CANDIDATE
    assert any(item.configured_term.lower() == "vrf" for item in result.evidence)


def test_candidate_chiller() -> None:
    result = screen("Manutenção preventiva e corretiva de chillers.")
    assert result.state is ScreeningStatus.CANDIDATE


def test_pending_maintenance_and_installation() -> None:
    result = screen("Manutenção e instalação de aparelhos de ar condicionado.")
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.MIXED_MAINTENANCE_INSTALLATION


def test_pending_supply_installation_maintenance() -> None:
    result = screen("Fornecimento de equipamentos com instalação e manutenção.")
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT


def test_pending_climatization_without_service() -> None:
    result = screen("Serviços para sistema de climatização.")
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.AMBIGUOUS_RELEVANT_CONTEXT


def test_pending_full_mixed_package() -> None:
    result = screen(
        "Contratação de solução de climatização incluindo fornecimento, "
        "instalação e manutenção."
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.MIXED_MAINTENANCE_INSTALLATION


def test_discarded_isolated_installation() -> None:
    result = screen("Instalação de aparelhos de ar condicionado.")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.ISOLATED_INSTALLATION


def test_discarded_equipment_purchase() -> None:
    first = screen("Aquisição de aparelhos de ar condicionado.")
    second = screen("Fornecimento de 30 condicionadores de ar.")
    assert first.reason_code is ReasonCode.ISOLATED_EQUIPMENT_PURCHASE
    assert second.reason_code is ReasonCode.ISOLATED_EQUIPMENT_PURCHASE
    assert first.state is ScreeningStatus.DISCARDED


def test_discarded_isolated_parts() -> None:
    first = screen("Aquisição de peças para aparelhos de ar condicionado.")
    second = screen("Fornecimento de componentes para sistema de climatização.")
    assert first.reason_code is ReasonCode.ISOLATED_PARTS_SUPPLY
    assert second.reason_code is ReasonCode.ISOLATED_PARTS_SUPPLY


def test_discarded_unrelated_pavement() -> None:
    result = screen("Contratação de serviços de pavimentação asfáltica.")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.NO_RELEVANT_SCOPE


def test_false_positive_vehicle_maintenance() -> None:
    result = screen("manutenção de veículos")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.NO_RELEVANT_SCOPE


def test_false_positive_cleaning_materials() -> None:
    result = screen("aquisição de material de limpeza")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.NO_RELEVANT_SCOPE


def test_false_positive_electrical_installation() -> None:
    result = screen("instalação elétrica")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.NO_RELEVANT_SCOPE


def test_false_positive_food_refrigeration() -> None:
    result = screen("refrigeração de alimentos")
    assert result.state is ScreeningStatus.DISCARDED
    assert result.reason_code is ReasonCode.NO_RELEVANT_SCOPE


def test_precedence_maintenance_plus_purchase_is_pending() -> None:
    result = screen(
        "Aquisição de aparelhos de ar condicionado com manutenção preventiva."
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.MIXED_MAINTENANCE_SUPPLY


def test_precedence_maintenance_plus_parts_is_pending() -> None:
    result = screen(
        "Fornecimento de peças e manutenção corretiva de sistema de climatização."
    )
    assert result.state is ScreeningStatus.PENDING
    assert result.reason_code is ReasonCode.MIXED_MAINTENANCE_SUPPLY


def test_empty_description_is_pending() -> None:
    empty = screen("")
    missing = screen(None)
    assert empty.reason_code is ReasonCode.EMPTY_DESCRIPTION
    assert missing.reason_code is ReasonCode.EMPTY_DESCRIPTION
    assert empty.state is ScreeningStatus.PENDING


def test_value_locality_and_modality_do_not_change_decision() -> None:
    description = (
        "Contratação de empresa especializada para manutenção preventiva e "
        "corretiva de aparelhos de ar condicionado."
    )
    first = screen(description)
    second = screen(description)
    assert first.state == second.state == ScreeningStatus.CANDIDATE
    assert Decimal("9999999.99") and "Acre" and "Concorrência"
    assert first.reason_code is second.reason_code


def test_two_profiles_produce_different_results() -> None:
    paving = ScreeningProfile(
        code="PAVES",
        name="Pavimentação",
        version="v1",
        context_terms=("pavimentação",),
        maintenance_terms=("serviços",),
        sanitization_terms=(),
        installation_terms=(),
        purchase_terms=(),
        parts_terms=(),
    )
    text = "Contratação de serviços de pavimentação asfáltica."
    usiar = screen(text)
    other = screen(text, paving)
    assert usiar.reason_code is ReasonCode.NO_RELEVANT_SCOPE
    assert other.state is ScreeningStatus.CANDIDATE


def test_profile_versions_are_distinct() -> None:
    v1 = usiar_v1()
    v2 = ScreeningProfile(
        code=v1.code,
        name=v1.name,
        version="v2",
        context_terms=v1.context_terms + ("pavimentação",),
        maintenance_terms=v1.maintenance_terms + ("serviços",),
        sanitization_terms=v1.sanitization_terms,
        installation_terms=v1.installation_terms,
        purchase_terms=v1.purchase_terms,
        parts_terms=v1.parts_terms,
    )
    assert v1.identity != v2.identity
    text = "Contratação de serviços de pavimentação asfáltica."
    assert screen(text, v1).reason_code is ReasonCode.NO_RELEVANT_SCOPE
    assert screen(text, v2).state is ScreeningStatus.CANDIDATE


def test_evidence_contains_configured_and_matched_terms() -> None:
    result = screen(
        "Contratação de empresa especializada para manutenção preventiva e "
        "corretiva de aparelhos de ar condicionado."
    )
    categories = {item.category for item in result.evidence}
    assert "context" in categories
    assert "maintenance" in categories
    assert any(item.field == "description" for item in result.evidence)
    assert any("manutenção" in item.configured_term for item in result.evidence)
    assert any(item.matched_text == "ar condicionado" for item in result.evidence)


def test_engine_never_returns_selected_or_confirmed() -> None:
    samples = (
        "Manutenção preventiva de ar condicionado.",
        "Instalação de aparelhos de ar condicionado.",
        "Aquisição de aparelhos de ar condicionado.",
        "Pavimentação asfáltica.",
        "",
    )
    for text in samples:
        result = screen(text)
        assert result.state in {
            ScreeningStatus.CANDIDATE,
            ScreeningStatus.PENDING,
            ScreeningStatus.DISCARDED,
        }


def test_evaluation_records_profile_and_observation() -> None:
    process_id = uuid4()
    observation_id = uuid4()
    profile = usiar_v1()
    result = ScreeningEngine().evaluate(
        profile,
        description="Manutenção preventiva de chillers.",
        process_id=process_id,
        observation_id=observation_id,
    )
    assert result.process_id == process_id
    assert result.observation_id == observation_id
    assert result.profile_code == "USIAR"
    assert result.profile_version == "v1"
    assert result.engine_version == "1"
