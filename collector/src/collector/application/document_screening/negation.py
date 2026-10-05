"""Negação explícita por cues tokenizados. Sem NLP."""

from __future__ import annotations

from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.screening.matching import find_matches
from collector.application.screening.normalize import tokenize


def is_negated(
    tokens: tuple[str, ...],
    match_start: int,
    policy: DocumentScreeningPolicy,
) -> bool:
    """Verdadeiro se um cue de negação é sufixo da janela imediatamente antes do termo.

    Frases longas ou subordinadas fora da janela não são interpretadas.
    Nesse caso o match permanece positivo e a decisão sobe para ambiguidade
    se o restante do conjunto não for decisivo.
    """

    if match_start <= 0:
        return False
    lookback = tokens[max(0, match_start - policy.negation_lookback_tokens) : match_start]
    if not lookback:
        return False
    for phrase in policy.negation_phrases:
        phrase_tokens = tokenize(phrase)
        if not phrase_tokens:
            continue
        width = len(phrase_tokens)
        if width > len(lookback):
            continue
        window = lookback[-width:]
        if window == phrase_tokens:
            return True
        if find_matches(lookback, phrase) and lookback[-len(phrase_tokens) :] == phrase_tokens:
            return True
    return False
