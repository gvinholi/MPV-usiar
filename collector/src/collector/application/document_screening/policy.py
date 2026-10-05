"""Limites centralizados da triagem documental. Sem números mágicos nas bordas."""

from dataclasses import dataclass

# ~120 de cada lado: snippet típico 150–300 caracteres, sem a página inteira.
DEFAULT_SNIPPET_RADIUS = 120
DEFAULT_SNIPPET_MAX_CHARS = 300
# Janela na mesma página: ~um parágrafo. Páginas distintas nunca combinam.
DEFAULT_PROXIMITY_TOKEN_WINDOW = 80
# Quantos tokens antes do termo olhar por negação explícita.
DEFAULT_NEGATION_LOOKBACK_TOKENS = 6

# Cues linguísticos, não termos de negócio USIAR. Configuráveis.
DEFAULT_NEGATION_PHRASES = (
    "nao",
    "sem",
    "nao havera",
    "nao inclui",
    "nao incluem",
    "nao contempla",
    "nao contemplam",
    "nao sera permitida",
    "nao serao permitidas",
    "nao sera permitido",
)


@dataclass(frozen=True)
class DocumentScreeningPolicy:
    snippet_radius: int = DEFAULT_SNIPPET_RADIUS
    snippet_max_chars: int = DEFAULT_SNIPPET_MAX_CHARS
    proximity_token_window: int = DEFAULT_PROXIMITY_TOKEN_WINDOW
    negation_lookback_tokens: int = DEFAULT_NEGATION_LOOKBACK_TOKENS
    negation_phrases: tuple[str, ...] = DEFAULT_NEGATION_PHRASES

    def __post_init__(self) -> None:
        if self.snippet_radius < 0:
            raise ValueError("snippet_radius não pode ser negativo")
        if self.snippet_max_chars < 1:
            raise ValueError("snippet_max_chars deve ser >= 1")
        if self.proximity_token_window < 0:
            raise ValueError("proximity_token_window não pode ser negativo")
        if self.negation_lookback_tokens < 0:
            raise ValueError("negation_lookback_tokens não pode ser negativo")
