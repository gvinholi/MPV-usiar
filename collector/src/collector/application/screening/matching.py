"""Casamento de termos por tokens consecutivos. Sem substring ingênua."""

from __future__ import annotations

from collector.application.screening.normalize import tokenize


def find_matches(tokens: tuple[str, ...], term: str) -> tuple[tuple[int, int], ...]:
    term_tokens = tokenize(term)
    if not term_tokens:
        return ()
    width = len(term_tokens)
    found: list[tuple[int, int]] = []
    for index in range(len(tokens) - width + 1):
        if tokens[index : index + width] == term_tokens:
            found.append((index, index + width))
    return tuple(found)


def matched_span(tokens: tuple[str, ...], start: int, end: int) -> str:
    return " ".join(tokens[start:end])
