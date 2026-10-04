"""Normalização textual determinística. Sem fuzzy e sem embeddings."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_SPACES = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_text(text: str) -> str:
    lowered = strip_accents(text.casefold())
    replaced = lowered.replace("-", " ").replace("/", " ")
    cleaned = _NON_ALNUM.sub(" ", replaced)
    return _SPACES.sub(" ", cleaned).strip()


def tokenize(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text)
    if not normalized:
        return ()
    return tuple(normalized.split(" "))
