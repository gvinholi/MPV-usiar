"""Normalização determinística e limites de palavra."""

from collector.application.screening.matching import find_matches
from collector.application.screening.normalize import normalize_text, tokenize


def test_case_and_accents() -> None:
    assert normalize_text("AR-CONDICIONADO") == "ar condicionado"
    assert normalize_text("Ar Condicionado") == "ar condicionado"
    assert normalize_text("climatização") == "climatizacao"


def test_hyphen_slash_and_punctuation() -> None:
    assert tokenize("VRF/VRV") == ("vrf", "vrv")
    assert tokenize("ar-condicionado.") == ("ar", "condicionado")
    assert tokenize("  manutenção   preventiva  ") == ("manutencao", "preventiva")


def test_term_matches_normalized_variants() -> None:
    tokens = tokenize("Manutenção de AR-CONDICIONADO")
    assert find_matches(tokens, "ar condicionado")
    assert find_matches(tokens, "ar-condicionado")
    assert find_matches(tokens, "manutenção")


def test_short_term_does_not_match_inside_unrelated_word() -> None:
    tokens = tokenize("particularidade do contrato")
    assert find_matches(tokens, "ar") == ()
    tokens = tokenize("manutenções extras")
    assert find_matches(tokens, "manutenção") == ()
