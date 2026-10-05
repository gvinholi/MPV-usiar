"""Normalização textual determinística. Sem fuzzy e sem embeddings."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class TokenSpan:
    """Token normalizado e intervalo no texto original (fim exclusivo)."""

    token: str
    start: int
    end: int


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_text(text: str) -> str:
    lowered = strip_accents(text.casefold())
    replaced = lowered.replace("-", " ").replace("/", " ")
    cleaned = _NON_ALNUM.sub(" ", replaced)
    return _SPACES.sub(" ", cleaned).strip()


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(span.token for span in tokenize_with_spans(text))


def tokenize_with_spans(text: str) -> tuple[TokenSpan, ...]:
    """Mesma tokenização de `tokenize`, com offsets no texto original.

    O casamento usa a forma normalizada; snippet e `matched_text` usam
    `text[start:end]` original. Caracteres combinantes não quebram o token.
    """

    spans: list[TokenSpan] = []
    index = 0
    length = len(text)
    while index < length:
        while index < length and _char_role(text[index]) == "sep":
            index += 1
        if index >= length:
            break
        start = index
        parts: list[str] = []
        while index < length:
            role, kept = _char_units(text[index])
            if role == "sep":
                break
            parts.extend(kept)
            index += 1
        if parts:
            spans.append(TokenSpan("".join(parts), start, index))
    return tuple(spans)


def _char_role(char: str) -> str:
    role, _kept = _char_units(char)
    return role


def _char_units(char: str) -> tuple[str, tuple[str, ...]]:
    folded = strip_accents(char.casefold())
    if not folded:
        return "extend", ()
    if folded in "-/" or _NON_ALNUM.fullmatch(folded):
        return "sep", ()
    kept = tuple(ch for ch in folded if ch.isalnum())
    if not kept:
        return "sep", ()
    return "keep", kept
