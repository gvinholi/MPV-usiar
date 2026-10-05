"""Snippet determinístico a partir do texto original. Sem reconstruir tokens."""

from __future__ import annotations

import unicodedata

from collector.application.document_screening.policy import DocumentScreeningPolicy


def context_snippet(
    text: str,
    start: int,
    end: int,
    policy: DocumentScreeningPolicy,
) -> str:
    if start < 0 or end < start or end > len(text):
        raise ValueError("intervalo do match fora do texto original")
    left = _safe_left(text, max(0, start - policy.snippet_radius))
    right = _safe_right(text, min(len(text), end + policy.snippet_radius))
    piece = text[left:right]
    if len(piece) > policy.snippet_max_chars:
        extra = len(piece) - policy.snippet_max_chars
        trim_left = extra // 2
        trim_right = extra - trim_left
        left = _safe_left(text, left + trim_left)
        right = _safe_right(text, right - trim_right)
        if right - left > policy.snippet_max_chars:
            right = left + policy.snippet_max_chars
            right = _safe_left(text, right) if right < len(text) else right
        piece = text[left:right]
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{piece}{suffix}"


def _safe_left(text: str, index: int) -> int:
    while index > 0 and index < len(text) and unicodedata.combining(text[index]):
        index -= 1
    return index


def _safe_right(text: str, index: int) -> int:
    while index < len(text) and unicodedata.combining(text[index]):
        index += 1
    return index
